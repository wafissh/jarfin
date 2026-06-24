"""
Database engine, session management, and initialization.
Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config import get_settings

# ── Engine & Session Factory ────────────────────────────────────────────────

settings = get_settings()

_is_sqlite = "sqlite" in settings.database_url

# Engine configuration varies by database backend
_engine_kwargs: dict = {
    "echo": False,
}

if _is_sqlite:
    # SQLite-specific: allow async usage from multiple threads
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL: connection pooling for production
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_pre_ping"] = True  # auto-reconnect stale connections

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Session Context Manager ────────────────────────────────────────────────

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Database Initialization ────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist."""
    from app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Run schema migrations using SQLAlchemy Inspector (database-agnostic)
        def migrate_schema(connection):
            from sqlalchemy import inspect, text

            inspector = inspect(connection)

            # ── Migrate 'transactions' table ────────────────────────────
            if inspector.has_table("transactions"):
                existing_cols = {
                    col["name"] for col in inspector.get_columns("transactions")
                }
                if "type" not in existing_cols:
                    connection.execute(
                        text(
                            "ALTER TABLE transactions ADD COLUMN type VARCHAR NOT NULL DEFAULT 'expense'"
                        )
                    )

            # ── Migrate 'users' table ───────────────────────────────────
            if inspector.has_table("users"):
                existing_cols = {
                    col["name"] for col in inspector.get_columns("users")
                }
                for col in [
                    "last_reminder_date",
                    "last_weekly_report_date",
                    "last_anomaly_alert_date",
                ]:
                    if col not in existing_cols:
                        connection.execute(
                            text(f"ALTER TABLE users ADD COLUMN {col} DATE")
                        )

        await conn.run_sync(migrate_schema)


async def close_db() -> None:
    """Dispose the engine and close all connections."""
    await engine.dispose()
