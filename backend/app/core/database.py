"""Async SQLAlchemy engine, session factory, and DB health check."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    # Return connections after 30 minutes idle (avoids stale connections)
    pool_recycle=1800,
    # Connection arguments for asyncpg
    connect_args={
        "server_settings": {
            "application_name": "fieldpro_backend",
        }
    },
)

# --------------------------------------------------------------------------- #
# Session factory
# --------------------------------------------------------------------------- #

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# --------------------------------------------------------------------------- #
# Declarative base
# --------------------------------------------------------------------------- #

class Base(DeclarativeBase):
    """All ORM models should inherit from this base."""


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session; rolled back on exception, closed always."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #

async def check_db_health() -> bool:
    """
    Attempt a lightweight query against the database.

    Returns True if successful, False otherwise. Logs errors but does not raise.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except OperationalError as exc:
        logger.error("database_health_check_failed", error=str(exc))
        return False


# --------------------------------------------------------------------------- #
# Test engine factory
# --------------------------------------------------------------------------- #

def create_test_engine(database_url: str | None = None):
    """Create a test engine against the test database."""
    url = database_url or settings.DATABASE_TEST_URL
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )
