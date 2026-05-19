"""
ARQ background worker process entry point.

Run with::

    python -m app.workers.main

or directly via arq::

    arq app.workers.main.WorkerSettings
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from arq import run_worker
from arq.connections import RedisSettings
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.workers.tasks import (
    expand_recurring_work_orders,
    generate_invoice_pdf,
    send_invoice_email,
    send_password_reset_email,
    send_work_order_notification,
    take_kpi_snapshot,
)

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Worker lifecycle hooks
# --------------------------------------------------------------------------- #

async def startup(ctx: dict[str, Any]) -> None:
    """
    Initialise shared resources and bind them to the worker context.

    Resources stored in *ctx* are available to every task function as
    ``ctx["db"]``, etc.
    """
    setup_logging(settings.LOG_LEVEL)
    logger.info("worker_startup", version=settings.APP_VERSION, environment=settings.ENVIRONMENT)

    from app.core.database import AsyncSessionLocal

    # Create a long-lived DB session for the worker process.
    # Tasks that need transactional isolation should create their own sessions.
    ctx["db"] = AsyncSessionLocal()
    logger.info("worker_db_session_created")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close shared resources gracefully."""
    db = ctx.get("db")
    if db is not None:
        await db.close()
        logger.info("worker_db_session_closed")

    logger.info("worker_shutdown")


# --------------------------------------------------------------------------- #
# Worker settings
# --------------------------------------------------------------------------- #

class WorkerSettings:
    """ARQ WorkerSettings class — discovered automatically by ``arq``."""

    functions: ClassVar = [
        send_password_reset_email,
        send_work_order_notification,
        expand_recurring_work_orders,
        generate_invoice_pdf,
        send_invoice_email,
        take_kpi_snapshot,
    ]

    # Worker MUST use ARQ_REDIS_URL (Redis DB 1) to match the enqueue path
    # in app.workers.tasks.enqueue_task. Using REDIS_URL (DB 0) means the
    # worker polls a different database than the backend writes to and
    # jobs sit forever unprocessed.
    redis_settings: RedisSettings = RedisSettings.from_dsn(settings.ARQ_REDIS_URL)

    # Maximum number of jobs to run concurrently.
    max_jobs: int = 10

    # Maximum wall-clock seconds a single job may run before being cancelled.
    job_timeout: int = settings.ARQ_JOB_TIMEOUT_SECONDS
    keep_result: int = settings.ARQ_KEEP_RESULT_SECONDS
    max_tries: int = settings.ARQ_MAX_TRIES
    retry_jobs: bool = True

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    asyncio.run(run_worker(WorkerSettings))  # type: ignore[arg-type]
