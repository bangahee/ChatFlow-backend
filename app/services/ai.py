from app.models import ChatLog


class AIServiceError(RuntimeError):
    """Base error for AI failures that can be mapped to an HTTP response."""


class AIUpstreamError(AIServiceError):
    """Raised when the upstream AI connection or response is invalid."""


class AIUnavailableError(AIServiceError):
    """Raised for rate limits and temporary upstream unavailability."""


class AITimeoutError(AIServiceError):
    """Raised after the configured AI timeout retries are exhausted."""


async def generate_ai_response(
    question: str,
    history: list[ChatLog],
    request_id: str,
) -> str:
    """AI integration seam implemented by 담당자 C."""
    raise AIUnavailableError("AI service implementation is not available")
