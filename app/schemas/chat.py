from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ChatItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    response: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ChatResponse(ChatItem):
    request_id: str = Field(min_length=1)


class ChatHistoryResponse(BaseModel):
    items: list[ChatItem]
    count: int = Field(ge=0)


class DeleteChatHistoryResponse(BaseModel):
    message: str
    deleted_count: int = Field(ge=0)
