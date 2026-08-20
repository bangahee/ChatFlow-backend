from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_ai_responder, get_current_user
from app.models import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatItem,
    ChatRequest,
    ChatResponse,
    DeleteChatHistoryResponse,
)
from app.services.ai import (
    AIServiceError,
    AITimeoutError,
    AIUnavailableError,
)
from app.services.chat import (
    AIResponder,
    ChatPersistenceError,
    clear_chat_history,
    create_chat_reply,
    get_chat_history,
)

router = APIRouter(tags=["chat"])


def map_ai_error(error: AIServiceError) -> HTTPException:
    if isinstance(error, AITimeoutError):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        detail = "AI 응답 시간이 초과되었습니다."
    elif isinstance(error, AIUnavailableError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "AI 서비스를 일시적으로 사용할 수 없습니다."
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = "AI 서비스 응답 처리 중 오류가 발생했습니다."
    return HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    ai_responder: Annotated[AIResponder, Depends(get_ai_responder)],
) -> ChatResponse:
    request_id = str(uuid4())
    try:
        chat = await create_chat_reply(
            db,
            current_user,
            payload.question,
            request_id,
            ai_responder,
        )
    except AIServiceError as exc:
        raise map_ai_error(exc) from exc
    except ChatPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대화 기록 저장 중 오류가 발생했습니다.",
        ) from exc

    return ChatResponse(
        id=chat.id,
        question=chat.question,
        response=chat.response,
        created_at=chat.created_at,
        request_id=request_id,
    )


@router.get(
    "/api/me/chats",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def list_chats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatHistoryResponse:
    try:
        chats = get_chat_history(db, current_user)
    except ChatPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대화 기록 조회 중 오류가 발생했습니다.",
        ) from exc

    items = [ChatItem.model_validate(chat) for chat in chats]
    return ChatHistoryResponse(items=items, count=len(items))


@router.delete(
    "/api/me/chats",
    response_model=DeleteChatHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def delete_chats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DeleteChatHistoryResponse:
    try:
        deleted_count = clear_chat_history(db, current_user)
    except ChatPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대화 기록 삭제 중 오류가 발생했습니다.",
        ) from exc

    return DeleteChatHistoryResponse(
        message="대화 기록이 삭제되었습니다.",
        deleted_count=deleted_count,
    )
