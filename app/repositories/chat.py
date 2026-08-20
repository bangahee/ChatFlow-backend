from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ChatLog


def get_recent_chats(
    db: Session,
    user_id: int,
    *,
    limit: int = 3,
) -> list[ChatLog]:
    """Return the user's latest chats ordered from oldest to newest."""
    statement = (
        select(ChatLog)
        .where(ChatLog.user_id == user_id)
        .order_by(ChatLog.created_at.desc(), ChatLog.id.desc())
        .limit(limit)
    )
    latest_first = list(db.scalars(statement))
    return list(reversed(latest_first))


def add_chat(
    db: Session,
    user_id: int,
    question: str,
    response: str,
) -> ChatLog:
    """Add a chat log to the current transaction without committing it."""
    chat = ChatLog(
        user_id=user_id,
        question=question,
        response=response,
    )
    db.add(chat)
    db.flush()
    return chat


def list_user_chats(db: Session, user_id: int) -> list[ChatLog]:
    """Return all chats for one user ordered from oldest to newest."""
    statement = (
        select(ChatLog)
        .where(ChatLog.user_id == user_id)
        .order_by(ChatLog.created_at.asc(), ChatLog.id.asc())
    )
    return list(db.scalars(statement))


def delete_user_chats(db: Session, user_id: int) -> int:
    """Delete one user's chats in the current transaction."""
    result = db.execute(delete(ChatLog).where(ChatLog.user_id == user_id))
    return int(result.rowcount or 0)
