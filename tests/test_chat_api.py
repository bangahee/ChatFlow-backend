from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_ai_responder
from app.services.ai import AITimeoutError, AIUnavailableError, AIUpstreamError


def register_and_login(
    client: TestClient,
    username: str = "chat_user",
) -> str:
    payload = {"username": username, "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def set_ai_responder(test_app: FastAPI, responder: Callable) -> None:
    test_app.dependency_overrides[get_ai_responder] = lambda: responder


def test_chat_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/chat", json={"question": "hello"})

    assert response.status_code == 401


def test_chat_uses_default_unavailable_ai_service(
    client: TestClient,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/api/chat",
        json={"question": "hello"},
        headers=auth_headers(token),
    )

    assert response.status_code == 503


def test_chat_success_is_saved_and_returned(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    token = register_and_login(client)

    async def fake_ai(question, history, request_id):
        assert question == "hello"
        assert history == []
        assert request_id
        return "hello response"

    set_ai_responder(test_app, fake_ai)
    response = client.post(
        "/api/chat",
        json={"question": "  hello  "},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question"] == "hello"
    assert body["response"] == "hello response"
    assert body["created_at"].endswith("Z")
    assert body["request_id"]

    history = client.get("/api/me/chats", headers=auth_headers(token))
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["response"] == "hello response"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AIUpstreamError("bad response"), 502),
        (AIUnavailableError("rate limited"), 503),
        (AITimeoutError("timed out"), 504),
    ],
)
def test_ai_errors_are_mapped_and_not_saved(
    client: TestClient,
    test_app: FastAPI,
    error: Exception,
    expected_status: int,
) -> None:
    token = register_and_login(client)

    async def failing_ai(_question, _history, _request_id):
        raise error

    set_ai_responder(test_app, failing_ai)
    response = client.post(
        "/api/chat",
        json={"question": "hello"},
        headers=auth_headers(token),
    )

    assert response.status_code == expected_status
    history = client.get("/api/me/chats", headers=auth_headers(token))
    assert history.json() == {"items": [], "count": 0}


def test_empty_ai_response_returns_502_without_saving(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    token = register_and_login(client)

    async def empty_ai(_question, _history, _request_id):
        return "   "

    set_ai_responder(test_app, empty_ai)
    response = client.post(
        "/api/chat",
        json={"question": "hello"},
        headers=auth_headers(token),
    )

    assert response.status_code == 502
    history = client.get("/api/me/chats", headers=auth_headers(token))
    assert history.json() == {"items": [], "count": 0}


def test_chat_history_and_deletion_are_isolated_by_user(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    first_token = register_and_login(client, "first_user")
    second_token = register_and_login(client, "second_user")

    async def fake_ai(question, _history, _request_id):
        return f"response to {question}"

    set_ai_responder(test_app, fake_ai)
    client.post(
        "/api/chat",
        json={"question": "first question"},
        headers=auth_headers(first_token),
    )
    client.post(
        "/api/chat",
        json={"question": "second question"},
        headers=auth_headers(second_token),
    )

    deleted = client.delete(
        "/api/me/chats",
        headers=auth_headers(first_token),
    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1
    first_history = client.get(
        "/api/me/chats",
        headers=auth_headers(first_token),
    ).json()
    second_history = client.get(
        "/api/me/chats",
        headers=auth_headers(second_token),
    ).json()
    assert first_history == {"items": [], "count": 0}
    assert second_history["count"] == 1
    assert second_history["items"][0]["question"] == "second question"
