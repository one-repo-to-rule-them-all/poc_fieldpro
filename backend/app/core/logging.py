"""
Structured logging configuration for FieldPro.

Usage
-----
Call ``setup_logging()`` once at application startup (inside the lifespan
handler).  Then obtain loggers anywhere in the codebase with::

    import structlog
    logger = structlog.get_logger(__name__)

or via the convenience alias exported from this module::

    from app.core.logging import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor

# Re-export for convenience so callers never need to import structlog directly.
get_logger = structlog.get_logger


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structlog for JSON output in production, pretty console in dev.

    This function is idempotent — calling it multiple times is safe.

    Parameters
    ----------
    log_level:
        A stdlib-compatible log level string, e.g. ``"DEBUG"``, ``"INFO"``,
        ``"WARNING"``.  Defaults to ``"INFO"``.
    """
    from app.core.config import settings  # deferred to avoid circular import

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    is_production = settings.is_production

    # ------------------------------------------------------------------
    # Shared processors (run for every log record regardless of renderer)
    # ------------------------------------------------------------------
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        # In production emit newline-delimited JSON — easy to ingest by log
        # aggregators (Datadog, Loki, CloudWatch, etc.).
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # In development use colourised, human-readable console output.
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            # Prepare the event dict for the final renderer.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ------------------------------------------------------------------
    # Configure stdlib logging to forward into structlog
    # ------------------------------------------------------------------
    formatter = structlog.stdlib.ProcessorFormatter(
        # These processors run only on records that come through stdlib.
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Avoid adding duplicate handlers if setup_logging is called more than once.
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    root_logger.setLevel(numeric_level)

    # Quiet down noisy third-party loggers in production.
    if is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
