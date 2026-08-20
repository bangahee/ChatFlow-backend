from fastapi.testclient import TestClient

from app.main import create_app


def test_docs_are_available() -> None:
    client = TestClient(create_app())

    response = client.get("/docs")

    assert response.status_code == 200


def test_prototype_routes_are_removed() -> None:
    client = TestClient(create_app())

    assert client.get("/").status_code == 404
    assert client.post("/test-user").status_code == 404
