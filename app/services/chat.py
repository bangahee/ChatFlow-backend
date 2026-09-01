import logging
import time
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.models import ChatLog, User
from app.observability import log_event
from app.repositories import chat as chat_repository
from app.repositories.protocols import ChatRepository
from app.services.ai import AIUpstreamError

AIResponder = Callable[[str, list[ChatLog], str], Awaitable[str]]
logger = logging.getLogger(__name__)


class ChatPersistenceError(RuntimeError):
    """Raised when chat data cannot be stored or retrieved safely."""


async def create_chat_reply(
    db: Session,
    current_user: User,
    question: str,
    request_id: str,
    ai_responder: AIResponder,
    repository: ChatRepository = chat_repository,
) -> ChatLog:
    """Generate an AI reply and persist it only after AI success."""
    history = repository.get_recent_chats(db, current_user.id, limit=3)
    ai_response = await ai_responder(question, history, request_id)
    if not isinstance(ai_response, str) or not ai_response.strip():
        raise AIUpstreamError("AI response is empty")

    save_started_at = time.monotonic()
    try:
        chat = repository.add_chat(
            db,
            current_user.id,
            question,
            ai_response,
        )
        db.commit()
        db.refresh(chat)
        log_event(
            logger,
            logging.INFO,
            "db_save_succeeded",
            request_id=request_id,
            operation="chat_create",
            user_id=current_user.id,
            chat_id=chat.id,
            latency_ms=round((time.monotonic() - save_started_at) * 1000, 2),
        )
        return chat
    except Exception as exc:
        db.rollback()
        log_event(
            logger,
            logging.ERROR,
            "db_save_failed",
            request_id=request_id,
            operation="chat_create",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            latency_ms=round((time.monotonic() - save_started_at) * 1000, 2),
        )
        raise ChatPersistenceError("Failed to save chat") from exc


def get_chat_history(
    db: Session,
    current_user: User,
    repository: ChatRepository = chat_repository,
) -> list[ChatLog]:
    """Return the current user's complete chat history."""
    try:
        return repository.list_user_chats(db, current_user.id)
    except Exception as exc:
        db.rollback()
        raise ChatPersistenceError("Failed to load chat history") from exc


def clear_chat_history(
    db: Session,
    current_user: User,
    repository: ChatRepository = chat_repository,
) -> int:
    """Delete and commit only the current user's chat history."""
    try:
        deleted_count = repository.delete_user_chats(db, current_user.id)
        db.commit()
        return deleted_count
    except Exception as exc:
        db.rollback()
        raise ChatPersistenceError("Failed to delete chat history") from exc
