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
        log_event(
            request_logger,
            logging.ERROR,
            "request_completed",
            **request_fields,
            status_code=500,
            latency_ms=round((time.monotonic() - started_at) * 1000, 2),
            error_type=type(exc).__name__,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    log_event(
        request_logger,
        logging.INFO,
        "request_completed",
        **request_fields,
        status_code=response.status_code,
        latency_ms=round((time.monotonic() - started_at) * 1000, 2),
        user_id=getattr(request.state, "user_id", None),
    )
    return response
