"""Async SQLAlchemy engine, session factory and declarative base.

Opened on startup and disposed on shutdown (`main.lifespan`), so the engine is
held in a module global like the other stores here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Uuid, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative root; `Base.metadata` is what Alembic generates against."""


# Native 16-byte uuid in the database, plain `str` on the Python side, so the
# domain and the wire format never handle a UUID object.
UuidText = Uuid(as_uuid=False)


def uuid_primary_key() -> Mapped[str]:
    """Id column filled by Postgres 18's `uuidv7()`: time-ordered, so inserts
    land at the right edge of the index instead of scattering across it."""
    return mapped_column(UuidText, primary_key=True, server_default=text("uuidv7()"))


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


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """One session and one transaction: commits on a clean exit, rolls back on
    an exception. Used directly rather than as a FastAPI dependency so the
    WebSocket handlers, which have no request scope, open one the same way."""
    if _sessions is None:
        raise RuntimeError("database not initialised")
    async with _sessions() as active:
        try:
            yield active
            await active.commit()
        except Exception:
            await active.rollback()
            raise


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
