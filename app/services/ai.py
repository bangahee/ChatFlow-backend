import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from app.config import Settings, get_settings
from app.models import ChatLog

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are ChatFlow, a helpful AI assistant. "
    "Answer the user's question clearly and safely."
)

QUOTA_ERROR_MARKERS = (
    "credit_balance",
    "insufficient_quota",
    "spend_limit",
    "usage_limit",
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


def _error_code(error: RateLimitError) -> str:
    code = getattr(error, "code", None)
    if code:
        return str(code).lower()

    body = getattr(error, "body", None)
    if isinstance(body, dict):
        nested_error = body.get("error")
        if isinstance(nested_error, dict) and nested_error.get("code"):
            return str(nested_error["code"]).lower()
        if body.get("code"):
            return str(body["code"]).lower()
    return ""


def _is_quota_error(error: RateLimitError) -> bool:
    code = _error_code(error)
    return any(marker in code for marker in QUOTA_ERROR_MARKERS)


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

    def _log_started(self, request_id: str, attempt: int, question: str) -> None:
        logger.info(
            "ai_call_started",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "question_length": len(question),
            },
        )

    def _log_succeeded(
        self,
        request_id: str,
        attempt: int,
        question: str,
        response: str,
        started_at: float,
    ) -> None:
        logger.info(
            "ai_call_succeeded",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "question_length": len(question),
                "response_length": len(response),
                "latency_ms": round((time.monotonic() - started_at) * 1000, 2),
            },
        )

    def _log_failed(
        self,
        request_id: str,
        attempt: int,
        question: str,
        error: BaseException,
        started_at: float,
    ) -> None:
        logger.warning(
            "ai_call_failed",
            extra={
                "request_id": request_id,
                "attempt": attempt,
                "question_length": len(question),
                "error_type": type(error).__name__,
                "latency_ms": round((time.monotonic() - started_at) * 1000, 2),
            },
        )

    async def generate(
        self,
        question: str,
        history: list[ChatLog],
        request_id: str,
    ) -> str:
        messages = build_ai_messages(question, history)
        total_attempts = self.settings.openai_max_retries + 1

        for attempt in range(1, total_attempts + 1):
            self._log_started(request_id, attempt, question)
            started_at = time.monotonic()
            try:
                async with asyncio.timeout(self.settings.openai_timeout_seconds):
                    response = await self._get_client().responses.create(
                        model=self.settings.openai_model,
                        input=messages,
                        store=False,
                    )

                output_text = getattr(response, "output_text", None)
                if not isinstance(output_text, str) or not output_text.strip():
                    raise AIUpstreamError("OpenAI response is empty")
                result = output_text.strip()
                self._log_succeeded(
                    request_id,
                    attempt,
                    question,
                    result,
                    started_at,
                )
                return result
            except AIServiceError as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                raise
            except (TimeoutError, APITimeoutError) as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                await self._retry_or_raise(
                    attempt=attempt,
                    final_error=AITimeoutError("OpenAI request timed out"),
                )
            except RateLimitError as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                unavailable = AIUnavailableError("OpenAI is rate limited or unavailable")
                if _is_quota_error(exc):
                    raise unavailable from exc
                await self._retry_or_raise(attempt=attempt, final_error=unavailable)
            except APIConnectionError as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                await self._retry_or_raise(
                    attempt=attempt,
                    final_error=AIUpstreamError("Could not connect to OpenAI"),
                )
            except APIStatusError as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                if exc.status_code >= 500:
                    await self._retry_or_raise(
                        attempt=attempt,
                        final_error=AIUnavailableError(
                            "OpenAI is temporarily unavailable"
                        ),
                    )
                else:
                    raise AIUpstreamError("OpenAI rejected the request") from exc
            except Exception as exc:
                self._log_failed(request_id, attempt, question, exc, started_at)
                raise AIUpstreamError("Unexpected OpenAI response failure") from exc

        raise AIUnavailableError("OpenAI response generation failed")


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
