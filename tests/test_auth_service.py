from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import Settings
from app.services.auth import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def create_test_settings(**overrides) -> Settings:
    values = {
        "secret_key": "test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "algorithm": "HS256",
        "access_token_expire_minutes": 60,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_hash_password_creates_argon2_hash_instead_of_plaintext() -> None:
    password = "password123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert hashed_password.startswith("$argon2")


def test_hash_password_uses_a_unique_salt() -> None:
    password = "password123"

    assert hash_password(password) != hash_password(password)


def test_verify_password_accepts_matching_password() -> None:
    password = "password123"
    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_verify_password_rejects_non_matching_password() -> None:
    hashed_password = hash_password("password123")

    assert verify_password("different-password", hashed_password) is False


def test_verify_password_rejects_unknown_hash_format() -> None:
    assert verify_password("password123", "not-a-password-hash") is False


def test_access_token_contains_required_claims() -> None:
    settings = create_test_settings()

    token = create_access_token(
        "chat_user",
        settings=settings,
        expires_delta=timedelta(seconds=60),
    )
    payload = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.algorithm],
    )

    assert payload["sub"] == "chat_user"
    assert payload["exp"] - payload["iat"] == 60


def test_decode_access_token_returns_subject() -> None:
    settings = create_test_settings()
    token = create_access_token("chat_user", settings=settings)

    assert decode_access_token(token, settings=settings) == "chat_user"


def test_create_access_token_rejects_empty_subject() -> None:
    with pytest.raises(ValueError, match="subject"):
        create_access_token("", settings=create_test_settings())


def test_expired_access_token_is_rejected() -> None:
    settings = create_test_settings()
    token = create_access_token(
        "chat_user",
        settings=settings,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenValidationError, match="Invalid access token"):
        decode_access_token(token, settings=settings)


def test_tampered_access_token_is_rejected() -> None:
    settings = create_test_settings()
    token = create_access_token("chat_user", settings=settings)
    header, payload, _signature = token.split(".")
    tampered_token = f"{header}.{payload}.invalid-signature"

    with pytest.raises(TokenValidationError, match="Invalid access token"):
        decode_access_token(tampered_token, settings=settings)


@pytest.mark.parametrize("missing_claim", ["sub", "iat", "exp"])
def test_access_token_with_missing_required_claim_is_rejected(
    missing_claim: str,
) -> None:
    settings = create_test_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "chat_user",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.pop(missing_claim)
    token = jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )

    with pytest.raises(TokenValidationError, match="Invalid access token"):
        decode_access_token(token, settings=settings)


def test_access_token_signed_with_different_secret_is_rejected() -> None:
    token = create_access_token("chat_user", settings=create_test_settings())
    other_settings = create_test_settings(
        secret_key="different-secret-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    )

    with pytest.raises(TokenValidationError, match="Invalid access token"):
        decode_access_token(token, settings=other_settings)


def test_access_token_using_unconfigured_algorithm_is_rejected() -> None:
    settings = create_test_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "chat_user", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.secret_key.get_secret_value(),
        algorithm="HS384",
    )

    with pytest.raises(TokenValidationError, match="Invalid access token"):
        decode_access_token(token, settings=settings)
