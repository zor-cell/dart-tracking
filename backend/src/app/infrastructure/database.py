"""Async SQLAlchemy engine, session factory and declarative base.

Opened on startup and disposed on shutdown (`main.lifespan`), so the engine is
held in a module global like the other stores here.
"""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative root; `Base.metadata` is what Alembic generates against."""


_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def init(url: str) -> None:
    """Build the engine. Connecting is lazy, so an unreachable server surfaces
    at the first query rather than here."""
    global _engine, _sessions
    _engine = create_async_engine(url, pool_pre_ping=True)
    _sessions = async_sessionmaker(_engine, expire_on_commit=False)


async def close() -> None:
    global _engine, _sessions
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessions = None


async def session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency handing out one session per request."""
    if _sessions is None:
        raise RuntimeError("database not initialised")
    async with _sessions() as active:
        yield active


async def ping() -> bool:
    """Whether the server answers (health check)."""
    if _engine is None:
        return False
    try:
        async with _engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True
