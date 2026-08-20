import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openai import APITimeoutError, AsyncOpenAI

from app.config import Settings, get_settings
from app.models import ChatLog

SYSTEM_PROMPT = (
    "You are ChatFlow, a helpful AI assistant. "
    "Answer the user's question clearly and safely."
)


class AIServiceError(RuntimeError):
    """Base error for AI failures that can be mapped to an HTTP response."""


class AIUpstreamError(AIServiceError):
    """Raised when the upstream AI connection or response is invalid."""


class AIUnavailableError(AIServiceError):
    """Raised for rate limits and temporary upstream unavailability."""


class AITimeoutError(AIServiceError):
    """Raised after the configured AI timeout retries are exhausted."""


class ResponsesResource(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class AIClient(Protocol):
    responses: ResponsesResource


AIResponder = Callable[[str, list[ChatLog], str], Awaitable[str]]
SleepCallable = Callable[[float], Awaitable[None]]


def build_ai_messages(
    question: str,
    history: list[ChatLog],
) -> list[dict[str, str]]:
    """Build system, recent history, and current-question messages in order."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for chat in history[-3:]:
        messages.append({"role": "user", "content": chat.question})
        messages.append({"role": "assistant", "content": chat.response})
    messages.append({"role": "user", "content": question})
    return messages


class AIService:
    """Generate responses with an app-configured async OpenAI client."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: AIClient | None = None,
        sleep: SleepCallable = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self._client = client
        self._sleep = sleep

    def _get_client(self) -> AIClient:
        if self._client is not None:
            return self._client

        api_key = self.settings.openai_api_key.get_secret_value().strip()
        if not api_key:
            raise AIUnavailableError("OpenAI API key is not configured")

        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=self.settings.openai_timeout_seconds,
            max_retries=0,
        )
        return self._client

    async def _retry_or_raise(
        self,
        *,
        attempt: int,
        final_error: AIServiceError,
    ) -> None:
        if attempt > self.settings.openai_max_retries:
            raise final_error
        await self._sleep(float(2 ** (attempt - 1)))

    async def generate(
        self,
        question: str,
        history: list[ChatLog],
        request_id: str,
    ) -> str:
        del request_id
        messages = build_ai_messages(question, history)
        total_attempts = self.settings.openai_max_retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                async with asyncio.timeout(self.settings.openai_timeout_seconds):
                    response = await self._get_client().responses.create(
                        model=self.settings.openai_model,
                        input=messages,
                        store=False,
                    )
            except (TimeoutError, APITimeoutError):
                await self._retry_or_raise(
                    attempt=attempt,
                    final_error=AITimeoutError("OpenAI request timed out"),
                )
                continue

            output_text = getattr(response, "output_text", None)
            if not isinstance(output_text, str) or not output_text.strip():
                raise AIUpstreamError("OpenAI response is empty")
            return output_text.strip()

        raise AITimeoutError("OpenAI request timed out")


def create_ai_responder(settings: Settings) -> AIResponder:
    """Create an app-configured responder while preserving the chat interface."""
    return AIService(settings).generate


async def generate_ai_response(
    question: str,
    history: list[ChatLog],
    request_id: str,
) -> str:
    """Generate a response using process-level settings."""
    return await AIService(get_settings()).generate(question, history, request_id)
