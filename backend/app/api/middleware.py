"""
FieldPro ASGI middleware.

RequestIDMiddleware   — assigns a unique request ID to every request.
AuditLogMiddleware   — logs mutations (POST/PUT/PATCH/DELETE) with timing.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger(__name__)

# Paths where AuditLogMiddleware should remain silent.
_AUDIT_SKIP_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/",
)

# HTTP methods that constitute mutations.
_MUTATION_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Reads ``X-Request-ID`` from the incoming request headers or generates a
    new UUID4.  The value is:

    1. Bound to the structlog context-var store so all log lines within the
       request carry ``request_id``.
    2. Echoed back on the response as ``X-Request-ID``.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind to structlog so every log statement inside this request carries
        # the request_id automatically.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Emits a structured log entry for every mutation request (POST, PUT,
    PATCH, DELETE) that does not belong to an exempt path.

    Log levels:
    - 2xx / 3xx  → INFO
    - 4xx        → WARNING
    - 5xx        → ERROR

    This middleware intentionally does NOT write to the database.  Persistent
    audit trails are the responsibility of the service layer.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        path = request.url.path

        # Only intercept mutations.
        if method not in _MUTATION_METHODS:
            return await call_next(request)

        # Skip exempt paths.
        if any(path.startswith(prefix) for prefix in _AUDIT_SKIP_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        status_code = response.status_code
        # Retrieve the request_id that RequestIDMiddleware already bound, or
        # fall back to the response header which RequestIDMiddleware sets.
        request_id = (
            structlog.contextvars.get_contextvars().get("request_id")
            or response.headers.get("X-Request-ID", "unknown")
        )

        log_data = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
        }

        if status_code < 400:
            logger.info("http_mutation", **log_data)
        elif status_code < 500:
            logger.warning("http_mutation_client_error", **log_data)
        else:
            logger.error("http_mutation_server_error", **log_data)

        return response
