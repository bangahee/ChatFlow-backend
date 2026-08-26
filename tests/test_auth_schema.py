from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)


schema_app = FastAPI()


@schema_app.post("/register")
def validate_register(payload: RegisterRequest) -> RegisterRequest:
    return payload


client = TestClient(schema_app)


@pytest.mark.parametrize("length", [3, 50])
def test_username_boundaries_are_accepted(length: int) -> None:
    payload = RegisterRequest(username="a" * length, password="password123")

    assert len(payload.username) == length


def test_username_is_trimmed() -> None:
    payload = LoginRequest(username="  chat_user  ", password="password123")

    assert payload.username == "chat_user"


@pytest.mark.parametrize(
    "username",
    [
        "ab",
        "a" * 51,
        "chat-user",
        "사용자",
    ],
)
def test_invalid_username_returns_422(username: str) -> None:
    response = client.post(
        "/register",
        json={"username": username, "password": "password123"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("length", [8, 128])
def test_password_boundaries_are_accepted_without_modification(length: int) -> None:
    password = " " + ("a" * (length - 2)) + " "

    payload = RegisterRequest(username="chat_user", password=password)

    assert payload.password == password


@pytest.mark.parametrize("length", [7, 129])
def test_invalid_password_length_returns_422(length: int) -> None:
    response = client.post(
        "/register",
        json={"username": "chat_user", "password": "a" * length},
    )

    assert response.status_code == 422


def test_unknown_request_field_returns_422() -> None:
    response = client.post(
        "/register",
        json={
            "username": "chat_user",
            "password": "password123",
            "admin": True,
        },
    )

    assert response.status_code == 422


def test_register_response_serializes_created_at_as_utc() -> None:
    response = RegisterResponse(
        id=1,
        username="chat_user",
        created_at=datetime(2026, 8, 20, 12, 0, tzinfo=timezone(timedelta(hours=9))),
    )

    assert response.model_dump(mode="json") == {
        "id": 1,
        "username": "chat_user",
        "created_at": "2026-08-20T03:00:00Z",
    }


def test_token_response_uses_bearer_contract() -> None:
    response = TokenResponse(access_token="jwt-token", expires_in=86400)

    assert response.model_dump() == {
        "access_token": "jwt-token",
        "token_type": "bearer",
        "expires_in": 86400,
    }
