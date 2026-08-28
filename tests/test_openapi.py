import pytest
from fastapi.testclient import TestClient


ERROR_RESPONSES = [
    ("/api/auth/register", "post", {"400", "422", "500"}),
    ("/api/auth/login", "post", {"401", "422"}),
    ("/api/me", "get", {"401"}),
    ("/api/chat", "post", {"401", "403", "422", "500", "502", "503", "504"}),
    ("/api/me/chats", "get", {"401", "403", "500"}),
    ("/api/me/chats", "delete", {"401", "403", "500"}),
    ("/api/admin/users", "get", {"401", "403", "500"}),
    (
        "/api/admin/users/{user_id}/chats",
        "get",
        {"401", "403", "404", "422", "500"},
    ),
]


@pytest.mark.parametrize(("path", "method", "expected_codes"), ERROR_RESPONSES)
def test_openapi_lists_endpoint_error_responses(
    client: TestClient,
    path: str,
    method: str,
    expected_codes: set[str],
) -> None:
    openapi = client.get("/openapi.json").json()

    responses = openapi["paths"][path][method]["responses"]

    assert expected_codes <= responses.keys()


@pytest.mark.parametrize(("path", "method", "expected_codes"), ERROR_RESPONSES)
def test_openapi_error_responses_include_descriptions_and_schemas(
    client: TestClient,
    path: str,
    method: str,
    expected_codes: set[str],
) -> None:
    openapi = client.get("/openapi.json").json()
    responses = openapi["paths"][path][method]["responses"]

    for code in expected_codes:
        response = responses[code]
        expected_schema = (
            "ValidationErrorResponse" if code == "422" else "ErrorResponse"
        )

        assert response["description"]
        assert response["content"]["application/json"]["schema"]["$ref"] == (
            f"#/components/schemas/{expected_schema}"
        )
