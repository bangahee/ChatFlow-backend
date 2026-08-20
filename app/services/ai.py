from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openai import AsyncOpenAI

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
    ) -> None:
        self.settings = settings
        self._client = client

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

    async def generate(
        self,
        question: str,
        history: list[ChatLog],
        request_id: str,
    ) -> str:
        del request_id
        response = await self._get_client().responses.create(
            model=self.settings.openai_model,
            input=build_ai_messages(question, history),
            store=False,
        )
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIUpstreamError("OpenAI response is empty")
        return output_text.strip()


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
