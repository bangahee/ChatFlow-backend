"""Safe structured logging helpers for request-level traceability."""

import json
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

request_logger = logging.getLogger("app.request")
auth_logger = logging.getLogger("app.auth")
audit_logger = logging.getLogger("app.audit")


def configure_application_logging(level: str) -> None:
    """Enable application logs and route them through Uvicorn's handlers."""
    application_logger = logging.getLogger("app")
    application_logger.setLevel(level)

    # Uvicorn configures its handlers before importing ``app.main:app`` in
    # production. Reusing those handlers makes INFO application events visible
    # in Railway without adding a second formatter or duplicating log lines.
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_handlers = uvicorn_logger.handlers
    while (
        not uvicorn_handlers
        and uvicorn_logger.propagate
        and uvicorn_logger.parent is not None
    ):
        uvicorn_logger = uvicorn_logger.parent
        uvicorn_handlers = uvicorn_logger.handlers

    if uvicorn_handlers:
        application_logger.handlers = list(uvicorn_handlers)
        application_logger.propagate = False


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Write an event as JSON while retaining fields on the LogRecord."""
    payload = {"event": event, **fields}
    logger.log(
        level,
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ),
        extra=payload,
    )


def get_request_id(request: Request) -> str:
    """Return the server-generated identifier for the current request."""
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id

    request_id = str(uuid4())
    request.state.request_id = request_id
    return request_id


def log_auth_failed(request: Request, reason: str) -> None:
    """Record an authentication failure without credentials or user input."""
    log_event(
        auth_logger,
        logging.WARNING,
        "auth_failed",
        request_id=get_request_id(request),
        method=request.method,
        path=request.url.path,
        reason=reason,
    )


def _safe_request_header(request: Request, name: str, limit: int) -> str | None:
    value = request.headers.get(name)
    return value[:limit] if value else None


def _persist_request_audit(
    request: Request,
    *,
    status_code: int,
    latency_ms: float,
    error_type: str | None,
) -> None:
    """Persist an allow-listed request summary without affecting the response."""
    if request.url.path == "/health":
        return

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        return

    try:
        from app.models import RequestLog

        with session_factory() as db:
            db.add(
                RequestLog(
                    request_id=get_request_id(request),
                    user_id=getattr(request.state, "user_id", None),
                    chat_id=getattr(request.state, "chat_id", None),
                    method=request.method,
                    path=request.url.path[:255],
                    status_code=status_code,
                    latency_ms=latency_ms,
                    origin=_safe_request_header(request, "origin", 255),
                    content_type=_safe_request_header(
                        request,
                        "content-type",
                        255,
                    ),
                    user_agent=_safe_request_header(request, "user-agent", 512),
                    error_type=error_type[:100] if error_type else None,
                )
            )
            db.commit()
    except Exception as exc:
        log_event(
            audit_logger,
            logging.ERROR,
            "request_audit_save_failed",
            request_id=get_request_id(request),
            error_type=type(exc).__name__,
        )


async def request_logging_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Trace the beginning and completion of every HTTP request."""
    request_id = get_request_id(request)
    started_at = time.monotonic()
    request_fields = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        # Only allow-listed, non-credential request metadata is recorded.
        "origin": _safe_request_header(request, "origin", 255),
        "content_type": _safe_request_header(request, "content-type", 255),
        "user_agent": _safe_request_header(request, "user-agent", 512),
    }
    log_event(
        request_logger,
        logging.INFO,
        "request_received",
        **request_fields,
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        latency_ms = round((time.monotonic() - started_at) * 1000, 2)
        error_type = type(exc).__name__
        _persist_request_audit(
            request,
            status_code=500,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        log_event(
            request_logger,
            logging.ERROR,
            "request_completed",
            **request_fields,
            status_code=500,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    latency_ms = round((time.monotonic() - started_at) * 1000, 2)
    error_type = (
        getattr(request.state, "error_type", None)
        or (f"HTTP_{response.status_code}" if response.status_code >= 400 else None)
    )
    _persist_request_audit(
        request,
        status_code=response.status_code,
        latency_ms=latency_ms,
        error_type=error_type,
    )
    log_event(
        request_logger,
        logging.INFO,
        "request_completed",
        **request_fields,
        status_code=response.status_code,
        latency_ms=latency_ms,
        user_id=getattr(request.state, "user_id", None),
        error_type=error_type,
    )
    return response
