import json
import logging

from fastapi.testclient import TestClient

from app.observability import configure_application_logging, log_event


def event_payloads(caplog) -> list[dict]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if hasattr(record, "event")
    ]


def test_application_logging_enables_info_events(caplog) -> None:
    application_logger = logging.getLogger("app")
    previous_level = application_logger.level

    try:
        configure_application_logging("INFO")
        log_event(
            logging.getLogger("app.production_check"),
            logging.INFO,
            "production_log_check",
            request_id="production-request-id",
        )
    finally:
        application_logger.setLevel(previous_level)

    payload = next(
        json.loads(record.getMessage())
        for record in caplog.records
        if getattr(record, "event", None) == "production_log_check"
    )
    assert payload == {
        "event": "production_log_check",
        "request_id": "production-request-id",
    }


def test_request_logs_share_server_request_id_and_completion_status(
    client: TestClient,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get("/health")

    payloads = event_payloads(caplog)
    assert [payload["event"] for payload in payloads] == [
        "request_received",
        "request_completed",
    ]
    assert payloads[0]["request_id"] == payloads[1]["request_id"]
    assert response.headers["x-request-id"] == payloads[0]["request_id"]
    assert payloads[0]["method"] == "GET"
    assert payloads[0]["path"] == "/health"
    assert payloads[1]["status_code"] == 200
    assert payloads[1]["user_id"] is None
    assert payloads[1]["latency_ms"] >= 0


def test_invalid_login_logs_reason_without_credentials(
    client: TestClient,
    caplog,
) -> None:
    secret_username = "private_user"
    secret_password = "private-password"

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        response = client.post(
            "/api/auth/login",
            json={"username": secret_username, "password": secret_password},
        )

    auth_record = next(
        record for record in caplog.records if record.event == "auth_failed"
    )
    assert response.status_code == 401
    assert auth_record.reason == "invalid_credentials"
    assert auth_record.request_id == response.headers["x-request-id"]
    assert auth_record.path == "/api/auth/login"
    assert secret_username not in caplog.text
    assert secret_password not in caplog.text


def test_missing_bearer_logs_auth_failure_and_completed_request(
    client: TestClient,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO):
        response = client.get("/api/me")

    payloads = event_payloads(caplog)
    failed = next(payload for payload in payloads if payload["event"] == "auth_failed")
    completed = next(
        payload for payload in payloads if payload["event"] == "request_completed"
    )
    assert response.status_code == 401
    assert failed["reason"] == "missing_or_invalid_bearer"
    assert failed["request_id"] == response.headers["x-request-id"]
    assert completed["request_id"] == failed["request_id"]
    assert completed["status_code"] == 401
