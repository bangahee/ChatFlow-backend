from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.models import ChatLog, User
from app.repositories.chat import (
    add_chat,
    delete_user_chats,
    get_recent_chats,
    list_user_chats,
)
from app.services.ai import AIUpstreamError

AIResponder = Callable[[str, list[ChatLog], str], Awaitable[str]]


class ChatPersistenceError(RuntimeError):
    """Raised when chat data cannot be stored or retrieved safely."""


async def create_chat_reply(
    db: Session,
    current_user: User,
    question: str,
    request_id: str,
    ai_responder: AIResponder,
) -> ChatLog:
    """Generate an AI reply and persist it only after AI success."""
    history = get_recent_chats(db, current_user.id, limit=3)
    ai_response = await ai_responder(question, history, request_id)
    if not isinstance(ai_response, str) or not ai_response.strip():
        raise AIUpstreamError("AI response is empty")

    try:
        chat = add_chat(
            db,
            current_user.id,
            question,
            ai_response,
        )
        db.commit()
        db.refresh(chat)
        return chat
    except Exception as exc:
        db.rollback()
        raise ChatPersistenceError("Failed to save chat") from exc


def get_chat_history(db: Session, current_user: User) -> list[ChatLog]:
    """Return the current user's complete chat history."""
    try:
        return list_user_chats(db, current_user.id)
    except Exception as exc:
        db.rollback()
        raise ChatPersistenceError("Failed to load chat history") from exc


def clear_chat_history(db: Session, current_user: User) -> int:
    """Delete and commit only the current user's chat history."""
    try:
        deleted_count = delete_user_chats(db, current_user.id)
        db.commit()
        return deleted_count
    except Exception as exc:
        db.rollback()
        raise ChatPersistenceError("Failed to delete chat history") from exc
