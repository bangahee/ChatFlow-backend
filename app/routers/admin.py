from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models import User
from app.schemas.admin import (
    AdminChatHistoryResponse,
    AdminUserListResponse,
    AdminUserSummary,
)
from app.schemas.chat import ChatItem
from app.schemas.common import ErrorResponse, ValidationErrorResponse
from app.services.admin import (
    AdminQueryError,
    get_admin_user_chat_history,
    get_admin_user_list,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_admin_authentication_responses = {
    401: {
        "model": ErrorResponse,
        "description": "로그인 필요 또는 Bearer Token 만료·변조·사용자 없음",
    },
    403: {
        "model": ErrorResponse,
        "description": "관리자 권한 없음",
    },
}
_list_admin_users_error_responses = {
    **_admin_authentication_responses,
    500: {
        "model": ErrorResponse,
        "description": "사용자 목록 조회 실패",
    },
}
_list_admin_user_chats_error_responses = {
    **_admin_authentication_responses,
    404: {
        "model": ErrorResponse,
        "description": "존재하지 않는 사용자",
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "올바르지 않은 사용자 식별자",
    },
    500: {
        "model": ErrorResponse,
        "description": "사용자 대화 기록 조회 실패",
    },
}


def to_user_summary(user: User, chat_count: int) -> AdminUserSummary:
    return AdminUserSummary(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        chat_count=chat_count,
    )


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    status_code=status.HTTP_200_OK,
    responses=_list_admin_users_error_responses,
)
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _current_admin: Annotated[User, Depends(get_current_admin)],
) -> AdminUserListResponse:
    try:
        users = get_admin_user_list(db)
    except AdminQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 목록을 불러오는 중 오류가 발생했습니다.",
        ) from exc

    items = [to_user_summary(user, chat_count) for user, chat_count in users]
    return AdminUserListResponse(items=items, count=len(items))


@router.get(
    "/users/{user_id}/chats",
    response_model=AdminChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    responses=_list_admin_user_chats_error_responses,
)
def list_admin_user_chats(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _current_admin: Annotated[User, Depends(get_current_admin)],
) -> AdminChatHistoryResponse:
    try:
        result = get_admin_user_chat_history(db, user_id)
    except AdminQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 대화 기록을 불러오는 중 오류가 발생했습니다.",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    user, chats = result
    return AdminChatHistoryResponse(
        user=to_user_summary(user, len(chats)),
        items=[ChatItem.model_validate(chat) for chat in chats],
        count=len(chats),
    )
