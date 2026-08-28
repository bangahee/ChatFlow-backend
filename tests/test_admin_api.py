from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User
from app.repositories.chat import add_chat


def register_and_login(client: TestClient, username: str) -> str:
    payload = {"username": username, "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def grant_admin(test_app: FastAPI, username: str) -> None:
    with test_app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == username))
        assert user is not None
        user.is_admin = True
        db.commit()


def add_user_chat(
    test_app: FastAPI,
    username: str,
    question: str,
    response: str,
) -> None:
    with test_app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == username))
        assert user is not None
        add_chat(db, user.id, question, response)
        db.commit()


def test_regular_user_cannot_access_administrator_routes(client: TestClient) -> None:
    token = register_and_login(client, "regular_user")

    response = client.get("/api/admin/users", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json() == {"detail": "관리자 권한이 필요합니다."}


def test_admin_can_list_all_users_with_aggregate_chat_counts(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    admin_token = register_and_login(client, "admin_user")
    register_and_login(client, "older_user")
    register_and_login(client, "newer_user")
    grant_admin(test_app, "admin_user")
    add_user_chat(test_app, "newer_user", "첫 질문", "첫 답변")
    add_user_chat(test_app, "newer_user", "둘째 질문", "둘째 답변")

    with test_app.state.session_factory() as db:
        admin = db.scalar(select(User).where(User.username == "admin_user"))
        older = db.scalar(select(User).where(User.username == "older_user"))
        newer = db.scalar(select(User).where(User.username == "newer_user"))
        assert admin is not None
        assert older is not None
        assert newer is not None
        admin.created_at = datetime(2026, 8, 19, tzinfo=timezone.utc)
        older.created_at = datetime(2026, 8, 20, tzinfo=timezone.utc)
        newer.created_at = datetime(2026, 8, 21, tzinfo=timezone.utc)
        db.commit()

    response = client.get("/api/admin/users", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    summaries = {item["username"]: item for item in body["items"]}
    assert "admin_user" not in summaries
    assert summaries["older_user"]["chat_count"] == 0
    assert summaries["newer_user"]["chat_count"] == 2
    assert body["items"][0]["username"] == "newer_user"


def test_admin_can_read_one_users_complete_chronological_history(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    admin_token = register_and_login(client, "admin_user")
    register_and_login(client, "chat_user")
    grant_admin(test_app, "admin_user")
    add_user_chat(test_app, "chat_user", "첫 질문", "첫 답변")
    add_user_chat(test_app, "chat_user", "둘째 질문", "둘째 답변")

    with test_app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "chat_user"))
        assert user is not None
        user_id = user.id

    response = client.get(
        f"/api/admin/users/{user_id}/chats",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "chat_user"
    assert body["user"]["chat_count"] == 2
    assert body["count"] == 2
    assert [item["question"] for item in body["items"]] == [
        "첫 질문",
        "둘째 질문",
    ]
    assert [item["response"] for item in body["items"]] == [
        "첫 답변",
        "둘째 답변",
    ]


def test_admin_history_returns_404_for_unknown_user(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    admin_token = register_and_login(client, "admin_user")
    grant_admin(test_app, "admin_user")

    response = client.get(
        "/api/admin/users/999/chats",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "사용자를 찾을 수 없습니다."}


def test_admin_accounts_are_hidden_from_administrator_history(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    admin_token = register_and_login(client, "admin_user")
    grant_admin(test_app, "admin_user")

    with test_app.state.session_factory() as db:
        admin = db.scalar(select(User).where(User.username == "admin_user"))
        assert admin is not None
        admin_id = admin.id

    response = client.get(
        f"/api/admin/users/{admin_id}/chats",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "사용자를 찾을 수 없습니다."}
