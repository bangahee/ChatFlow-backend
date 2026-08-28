from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.models import User
from app.services.auth import create_access_token


def register_user(
    client: TestClient,
    username: str = "chat_user",
    password: str = "password123",
):
    return client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )


def login_user(
    client: TestClient,
    username: str = "chat_user",
    password: str = "password123",
):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def test_register_creates_hashed_user(client: TestClient, test_app) -> None:
    response = register_user(client)

    assert response.status_code == 201
    assert response.json()["username"] == "chat_user"
    assert response.json()["is_admin"] is False
    assert response.json()["created_at"].endswith("Z")

    with test_app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "chat_user"))
        assert user is not None
        assert user.hashed_password != "password123"
        assert user.hashed_password.startswith("$argon2")


def test_duplicate_username_returns_400(client: TestClient) -> None:
    assert register_user(client).status_code == 201

    response = register_user(client)

    assert response.status_code == 400
    assert response.json() == {"detail": "이미 존재하는 아이디입니다."}


def test_login_returns_bearer_token(client: TestClient) -> None:
    register_user(client)

    response = login_user(client)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 86400
    assert response.json()["access_token"]


def test_unknown_user_and_wrong_password_return_same_401(client: TestClient) -> None:
    register_user(client)

    unknown = login_user(client, username="unknown_user")
    wrong_password = login_user(client, password="wrong-password")

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()
    assert unknown.headers["www-authenticate"] == "Bearer"


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_returns_token_user(client: TestClient) -> None:
    register_user(client)
    token = login_user(client).json()["access_token"]

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "chat_user"
    assert response.json()["is_admin"] is False


def test_me_rejects_tampered_token(client: TestClient) -> None:
    register_user(client)
    token = login_user(client).json()["access_token"]

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}tampered"},
    )

    assert response.status_code == 401


def test_me_rejects_expired_token(client: TestClient, test_app) -> None:
    register_user(client)
    token = create_access_token(
        "chat_user",
        settings=test_app.state.settings,
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_me_rejects_token_when_user_was_deleted(
    client: TestClient,
    test_app,
) -> None:
    register_user(client)
    token = login_user(client).json()["access_token"]
    with test_app.state.session_factory() as db:
        db.execute(delete(User).where(User.username == "chat_user"))
        db.commit()

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
