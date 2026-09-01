"""Structural interfaces for persistence adapters used by services."""

from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.models import ChatLog


@runtime_checkable
class ChatRepository(Protocol):
    """Define the chat persistence operations required by the service layer."""

    def get_recent_chats(
        self,
        db: Session,
        user_id: int,
        *,
        limit: int = 3,
    ) -> list[ChatLog]: ...

    def add_chat(
        self,
        db: Session,
        user_id: int,
        question: str,
        response: str,
    ) -> ChatLog: ...

    def list_user_chats(self, db: Session, user_id: int) -> list[ChatLog]: ...

    def delete_user_chats(self, db: Session, user_id: int) -> int: ...
