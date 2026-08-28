from sqlalchemy.orm import Session

from app.models import ChatLog, User
from app.repositories.chat import list_user_chats
from app.repositories.user import (
    get_non_admin_user_by_id,
    list_users_with_chat_counts,
)


class AdminQueryError(RuntimeError):
    """Raised when an administrator read query cannot complete safely."""


def get_admin_user_list(db: Session) -> list[tuple[User, int]]:
    """Return every user and aggregate chat count for the administrator view."""
    try:
        return list_users_with_chat_counts(db)
    except Exception as exc:
        db.rollback()
        raise AdminQueryError("Failed to load administrator user list") from exc


def get_admin_user_chat_history(
    db: Session,
    user_id: int,
) -> tuple[User, list[ChatLog]] | None:
    """Return one existing user and its complete chronological chat history."""
    try:
        user = get_non_admin_user_by_id(db, user_id)
        if user is None:
            return None
        return user, list_user_chats(db, user.id)
    except Exception as exc:
        db.rollback()
        raise AdminQueryError("Failed to load administrator chat history") from exc
