from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import User
from app.repositories.user import add_user, get_user_by_username

password_hash = PasswordHash.recommended()


class TokenValidationError(ValueError):
    """Raised when an access token cannot identify a valid subject."""


class DuplicateUsernameError(ValueError):
    """Raised when a username cannot be registered more than once."""


class InvalidCredentialsError(ValueError):
    """Raised when a login attempt cannot be authenticated."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with the recommended Argon2 settings."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        return False


def register_user(db: Session, username: str, password: str) -> User:
    """Create and commit a user with a securely hashed password."""
    if get_user_by_username(db, username) is not None:
        raise DuplicateUsernameError("Username already exists")

    try:
        user = add_user(db, username, hash_password(password))
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateUsernameError("Username already exists") from exc
    except Exception:
        db.rollback()
        raise


def authenticate_user(db: Session, username: str, password: str) -> User:
    """Return the authenticated user without revealing failure details."""
    user = get_user_by_username(db, username)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid username or password")
    return user


def create_access_token(
    subject: str,
    *,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access token for a username subject."""
    if not subject:
        raise ValueError("Token subject must not be empty")

    app_settings = settings or get_settings()
    issued_at = datetime.now(timezone.utc)
    lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=app_settings.access_token_expire_minutes)
    )
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    return jwt.encode(
        payload,
        app_settings.secret_key.get_secret_value(),
        algorithm=app_settings.algorithm,
    )


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> str:
    """Validate an access token and return its username subject."""
    app_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            app_settings.secret_key.get_secret_value(),
            algorithms=[app_settings.algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject:
            raise TokenValidationError("Invalid access token")
        return subject
    except InvalidTokenError as exc:
        raise TokenValidationError("Invalid access token") from exc
