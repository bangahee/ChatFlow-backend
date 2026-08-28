from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatLog, User


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return the user with the exact username, if one exists."""
    statement = select(User).where(User.username == username)
    return db.scalar(statement)


def get_non_admin_user_by_id(db: Session, user_id: int) -> User | None:
    """Return one regular user by primary key without exposing administrators."""
    statement = select(User).where(
        User.id == user_id,
        User.is_admin.is_(False),
    )
    return db.scalar(statement)


def list_users_with_chat_counts(db: Session) -> list[tuple[User, int]]:
    """Return every regular user with its chat count in one aggregate query."""
    statement = (
        select(User, func.count(ChatLog.id).label("chat_count"))
        .where(User.is_admin.is_(False))
        .outerjoin(ChatLog, ChatLog.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc(), User.id.desc())
    )
    return [
        (user, int(chat_count))
        for user, chat_count in db.execute(statement)
    ]


def add_user(db: Session, username: str, hashed_password: str) -> User:
    """Add a user to the current transaction without committing it."""
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user
