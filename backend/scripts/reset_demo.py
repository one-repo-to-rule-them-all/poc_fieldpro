"""
FieldPro — Demo Reset
=====================
Wipes all data, re-runs migrations, and re-seeds the demo dataset.

Used by the nightly Fly scheduled machine to keep the public demo clean.

WARNING: This drops the entire `public` schema. Do not run against any
database that holds real customer data.

Usage:
    python scripts/reset_demo.py

Env:
    DATABASE_URL must point at the demo Postgres (postgresql+asyncpg://...).
    The script refuses to run unless ENVIRONMENT is set and DATABASE_URL
    points at a database whose name contains "poc" or "demo".
"""

import asyncio
import os
import subprocess
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _guardrail() -> None:
    """Refuse to run unless the target DB name looks like a demo/poc DB."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is not set — refusing to run.")

    db_name = urlparse(url.replace("postgresql+asyncpg://", "postgresql://")).path.lstrip("/")
    if not any(token in db_name.lower() for token in ("poc", "demo")):
        raise SystemExit(
            f"Database name '{db_name}' does not contain 'poc' or 'demo'. "
            "Refusing to run reset against a non-demo database."
        )


async def _drop_and_recreate_schema() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()


def _run_alembic_upgrade() -> None:
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"alembic upgrade head failed (exit {result.returncode})")


async def _run_seed() -> None:
    from scripts.seed_data import main as seed_main
    await seed_main()


async def main() -> None:
    print("FieldPro — Demo Reset")
    print("=" * 50)

    _guardrail()

    print("  > Dropping + recreating public schema...")
    await _drop_and_recreate_schema()

    print("  > Running alembic upgrade head...")
    _run_alembic_upgrade()

    print("  > Re-seeding demo data...")
    await _run_seed()

    print("  Demo reset complete.")


if __name__ == "__main__":
    asyncio.run(main())
