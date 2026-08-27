from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_ai_responder, get_current_user
from app.models import User
from app.observability import get_request_id
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatItem,
    ChatRequest,
    ChatResponse,
    DeleteChatHistoryResponse,
)
from app.schemas.common import ErrorResponse, ValidationErrorResponse
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

_create_chat_error_responses = {
    401: {
        "model": ErrorResponse,
        "description": "Bearer Token 누락, 만료, 변조 또는 사용자 없음",
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "공백 질문 또는 500자 초과",
    },
    500: {
        "model": ErrorResponse,
        "description": "대화 기록 저장 실패",
    },
    502: {
        "model": ErrorResponse,
        "description": "OpenAI 연결 실패 또는 잘못된 응답",
    },
    503: {
        "model": ErrorResponse,
        "description": "OpenAI 요청 한도 또는 일시적 사용 불가",
    },
    504: {
        "model": ErrorResponse,
        "description": "OpenAI 호출 최종 타임아웃",
    },
}
_list_chat_error_responses = {
    401: {
        "model": ErrorResponse,
        "description": "Bearer Token 누락, 만료, 변조 또는 사용자 없음",
    },
    500: {
        "model": ErrorResponse,
        "description": "대화 기록 조회 실패",
    },
}
_delete_chat_error_responses = {
    401: {
        "model": ErrorResponse,
        "description": "Bearer Token 누락, 만료, 변조 또는 사용자 없음",
    },
    500: {
        "model": ErrorResponse,
        "description": "대화 기록 삭제 실패",
    },
}


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
    responses=_create_chat_error_responses,
)
async def create_chat(
    request: Request,
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    ai_responder: Annotated[AIResponder, Depends(get_ai_responder)],
) -> ChatResponse:
    request_id = get_request_id(request)
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
    responses=_list_chat_error_responses,
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
    responses=_delete_chat_error_responses,
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
