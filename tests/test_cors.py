from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


ALLOWED_ORIGIN = "https://frontend.example.com"
DISALLOWED_ORIGIN = "https://untrusted.example.com"


def create_test_client() -> TestClient:
    settings = Settings(_env_file=None, cors_origins=ALLOWED_ORIGIN)
    return TestClient(create_app(settings))


def test_allowed_origin_preflight_is_accepted() -> None:
    client = create_test_client()

    response = client.options(
        "/docs",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_disallowed_origin_preflight_is_rejected() -> None:
    client = create_test_client()

    response = client.options(
        "/docs",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origin_is_added_to_regular_response() -> None:
    client = create_test_client()

    response = client.get("/docs", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
