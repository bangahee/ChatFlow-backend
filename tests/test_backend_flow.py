from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_ai_responder


def test_authenticated_chat_lifecycle_with_mock_ai(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    credentials = {"username": "flow_user", "password": "password123"}

    registered = client.post("/api/auth/register", json=credentials)
    assert registered.status_code == 201

    logged_in = client.post("/api/auth/login", json=credentials)
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    current_user = client.get("/api/me", headers=headers)
    assert current_user.status_code == 200
    assert current_user.json()["username"] == "flow_user"

    async def fake_ai(question, history, request_id):
        assert question == "통합 테스트 질문"
        assert history == []
        assert request_id
        return "통합 테스트 응답"

    test_app.dependency_overrides[get_ai_responder] = lambda: fake_ai

    created = client.post(
        "/api/chat",
        json={"question": "통합 테스트 질문"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["response"] == "통합 테스트 응답"
    assert created.headers["x-request-id"] == created.json()["request_id"]

    history = client.get("/api/me/chats", headers=headers)
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["id"] == created.json()["id"]

    deleted = client.delete("/api/me/chats", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1

    empty_history = client.get("/api/me/chats", headers=headers)
    assert empty_history.status_code == 200
    assert empty_history.json() == {"items": [], "count": 0}
