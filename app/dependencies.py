"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_db
from app.models import User
from app.repositories.user import get_user_by_username
from app.services.ai import generate_ai_response
from app.services.auth import TokenValidationError, decode_access_token
from app.services.chat import AIResponder

bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_ai_responder() -> AIResponder:
    """Return the configured production AI responder."""
    return generate_ai_response


def unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 자격 증명이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    """Resolve a valid bearer token to an existing database user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized_exception()

    try:
        username = decode_access_token(credentials.credentials, settings=settings)
    except TokenValidationError as exc:
        raise unauthorized_exception() from exc

    user = get_user_by_username(db, username)
    if user is None:
        raise unauthorized_exception()
    return user
