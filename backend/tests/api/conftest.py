"""Runs the app against its own Postgres database and Redis db, rebuilt from the
migrations once per run and emptied before every test."""

import asyncio
import os
from collections.abc import Callable, Iterator
from email.message import EmailMessage

import asyncpg
import pytest
from alembic import command

from app.infrastructure.config import Settings, get_settings

_TEST_SUFFIX = "_test"

_base = Settings()
if not _base.postgres_db.endswith(_TEST_SUFFIX):
    os.environ["POSTGRES_DB"] = _base.postgres_db + _TEST_SUFFIX
os.environ.setdefault("REDIS_DB", "15")
get_settings.cache_clear()
assert get_settings().postgres_db.endswith(_TEST_SUFFIX), "tests must never touch a real database"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.api import tables  # noqa: E402, F401
from app.infrastructure import database, mailer, redis_client  # noqa: E402
from app.infrastructure.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from tests.api.support import Api, Session, alembic_config  # noqa: E402


async def _recreate_schema(settings: Settings) -> None:
    credentials = {
        "user": settings.postgres_user,
        "password": settings.postgres_password,
        "host": settings.postgres_host,
        "port": settings.postgres_port,
    }
    server = await asyncpg.connect(database="postgres", **credentials)
    try:
        if not await server.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", settings.postgres_db
        ):
            await server.execute(f'CREATE DATABASE "{settings.postgres_db}"')
    finally:
        await server.close()

    test_db = await asyncpg.connect(database=settings.postgres_db, **credentials)
    try:
        await test_db.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    finally:
        await test_db.close()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    asyncio.run(_recreate_schema(get_settings()))
    command.upgrade(alembic_config(), "head")
    with TestClient(app) as test_client:
        yield test_client


async def _reset() -> None:
    names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with database.session_scope() as session:
        await session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    await redis_client.client().flushdb()


@pytest.fixture(autouse=True)
def mails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Every mail the app sends during the test, instead of SMTP."""
    client.portal.call(_reset)
    outbox: list[EmailMessage] = []

    async def capture(message: EmailMessage) -> None:
        outbox.append(message)

    monkeypatch.setattr(mailer, "send", capture)
    return outbox


@pytest.fixture
def session(client: TestClient) -> Session:
    return Session(client)


@pytest.fixture
def anon(client: TestClient) -> Api:
    return Api(client)


@pytest.fixture
def register(session: Session) -> Callable[..., Api]:
    return session.register
