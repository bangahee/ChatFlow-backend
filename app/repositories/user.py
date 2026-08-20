from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return the user with the exact username, if one exists."""
    statement = select(User).where(User.username == username)
    return db.scalar(statement)


def add_user(db: Session, username: str, hashed_password: str) -> User:
    """Add a user to the current transaction without committing it."""
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user
