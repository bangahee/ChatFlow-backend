from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.dependencies import get_ai_responder
from app.models import RequestLog


def test_health_returns_ok_without_ai_call(
    client: TestClient,
    test_app,
) -> None:
    def fail_if_resolved():
        raise AssertionError("health check must not resolve the AI dependency")

    test_app.dependency_overrides[get_ai_responder] = fail_if_resolved

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    with test_app.state.session_factory() as db:
        assert db.scalar(select(func.count(RequestLog.id))) == 0
