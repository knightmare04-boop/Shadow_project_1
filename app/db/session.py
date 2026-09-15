"""Async SQLAlchemy engine + session factory.

Pool sizing is explicit (see app.core.config) because Module 9's concurrency
tests (50/200/500 virtual users) need a known, tunable ceiling to reason about
— an unbounded or default pool makes "where does it degrade" unanswerable.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

_engine_kwargs = dict(
    echo=False,
    pool_pre_ping=True,
)
if settings.env == "test":
    # Testcontainers spins a fresh DB per test session; a bounded pool across
    # short-lived event loops causes cross-loop connection errors.
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. One session per request, closed on exit."""
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """For use outside request scope (background jobs, scripts, tests)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
