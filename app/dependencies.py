"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_db
from app.models import User
from app.observability import log_auth_failed
from app.repositories.user import get_user_by_username
from app.services.ai import create_ai_responder
from app.services.auth import TokenValidationError, decode_access_token
from app.services.chat import AIResponder

bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_ai_responder(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AIResponder:
    """Return the configured production AI responder."""
    return create_ai_responder(settings)


def unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 자격 증명이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="관리자 권한이 필요합니다.",
    )


def admin_chat_forbidden_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="관리자 계정은 채팅을 사용할 수 없습니다.",
    )


def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    """Resolve a valid bearer token to an existing database user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        log_auth_failed(request, "missing_or_invalid_bearer")
        raise unauthorized_exception()

    try:
        username = decode_access_token(credentials.credentials, settings=settings)
    except TokenValidationError as exc:
        log_auth_failed(request, "invalid_or_expired_token")
        raise unauthorized_exception() from exc

    user = get_user_by_username(db, username)
    if user is None:
        log_auth_failed(request, "user_not_found")
        raise unauthorized_exception()
    request.state.user_id = user.id
    return user


def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the current database user to hold the persisted admin role."""
    if not current_user.is_admin:
        raise forbidden_exception()
    return current_user


def get_current_chat_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require a non-administrator account for user chat operations."""
    if current_user.is_admin:
        raise admin_chat_forbidden_exception()
    return current_user
