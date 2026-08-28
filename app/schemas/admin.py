from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import ChatItem


class AdminUserSummary(BaseModel):
    id: int
    username: str
    created_at: datetime
    chat_count: int = Field(ge=0)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AdminUserListResponse(BaseModel):
    items: list[AdminUserSummary]
    count: int = Field(ge=0)


class AdminChatHistoryResponse(BaseModel):
    user: AdminUserSummary
    items: list[ChatItem]
    count: int = Field(ge=0)
