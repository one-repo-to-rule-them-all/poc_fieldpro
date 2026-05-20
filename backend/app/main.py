"""FieldPro FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.logging import setup_logging

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Sentry initialisation (must happen before app creation)
# --------------------------------------------------------------------------- #

def _init_sentry() -> None:
    """Initialise Sentry SDK only when a DSN is configured."""
    if not settings.SENTRY_DSN:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.2 if settings.is_production else 1.0,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        send_default_pii=False,
    )
    logger.info("sentry_initialised", dsn_configured=True)


_init_sentry()


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown logic."""
    setup_logging(settings.LOG_LEVEL)

    # Register Phase 3 audit listeners on the allowlist of models.
    # See app/core/audit/listeners.py — AuditListener.AUDITED_MODELS.
    from app.core.audit import AuditListener
    AuditListener.register()

    logger.info(
        "startup",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    yield
    logger.info("shutdown", version=settings.APP_VERSION)


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)


# --------------------------------------------------------------------------- #
# Middleware  (outermost → innermost, i.e. added last executes first)
# --------------------------------------------------------------------------- #

# 1. Sentry request handler (conditionally added)
if settings.SENTRY_DSN:
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
    app.add_middleware(SentryAsgiMiddleware)

# 2. RequestIDMiddleware — must run before AuditLog so request_id is bound
from app.api.middleware import AuditLogMiddleware, RequestIDMiddleware  # noqa: E402

app.add_middleware(RequestIDMiddleware)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. TrustedHost
_allowed_hosts: list[str] = [
    h.strip()
    for h in settings.ALLOWED_HOSTS.split(",")
    if h.strip()
] or ["*"]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

# 5. GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 6. AuditLog (logs mutations; must be innermost so it has the final status code)
app.add_middleware(AuditLogMiddleware)


# --------------------------------------------------------------------------- #
# Exception handlers
# --------------------------------------------------------------------------- #

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = structlog.contextvars.get_contextvars().get("request_id", "unknown")
    logger.warning(
        "request_validation_error",
        path=str(request.url),
        errors=exc.errors(),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
                "request_id": request_id,
            }
        },
    )


from fastapi import HTTPException  # noqa: E402


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    request_id = structlog.contextvars.get_contextvars().get("request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _status_to_code(exc.status_code),
                "message": exc.detail,
                "request_id": request_id,
            }
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    request_id = structlog.contextvars.get_contextvars().get("request_id", "unknown")
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        path=str(request.url),
        method=request.method,
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": request_id,
            }
        },
    )


def _status_to_code(status_code: int) -> str:
    """Map HTTP status codes to a short error code string."""
    _map: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        410: "GONE",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return _map.get(status_code, f"HTTP_{status_code}")


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
    tags=["ops"],
    summary="Health check",
    response_model=dict[str, Any],
)
async def health_check() -> dict[str, Any]:
    """
    Liveness + readiness probe.

    Returns the status of the API, database, and Redis connections.
    """
    from app.core.database import check_db_health

    db_ok = await check_db_health()

    # Redis health check
    redis_ok: bool
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        )
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception as exc:
        logger.warning("redis_health_check_failed", error=str(exc))
        redis_ok = False

    overall = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
