"""Reads and writes an account's settings."""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.settings.domain.app_settings import DEFAULTS, AppSettings
from app.api.features.settings.domain.filter_use import FilterUse
from app.api.features.settings.persistence.user_settings import UserSettingsTable


class SettingsRepository:
    async def get(self, session: AsyncSession, user_id: str) -> AppSettings:
        """An account that has never changed anything has no row, and gets the
        defaults — the same answer an anonymous session gets."""
        row = (
            await session.execute(
                select(UserSettingsTable).where(UserSettingsTable.user_id == user_id)
            )
        ).scalar_one_or_none()

        if row is None:
            return DEFAULTS
        return AppSettings(
            advance_on_pull=row.advance_on_pull,
            evaluation_enabled=row.evaluation_enabled,
            preferred_doubles=tuple(row.preferred_doubles),
        )

    async def save(
        self, session: AsyncSession, user_id: str, settings: AppSettings
    ) -> None:
        """Write the whole set. Upsert rather than read-then-write: the first
        change an account makes is also the row's insert."""
        values = _columns(settings)
        await session.execute(
            insert(UserSettingsTable)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=["user_id"], set_={**values, "updated_at": func.now()}
            )
        )

    async def filter_usage(self, session: AsyncSession, user_id: str) -> tuple[FilterUse, ...]:
        rows = (
            await session.execute(
                select(UserSettingsTable.filter_usage).where(UserSettingsTable.user_id == user_id)
            )
        ).scalar_one_or_none()
        return tuple(_to_use(row) for row in rows or [])

    async def save_filter_usage(
        self, session: AsyncSession, user_id: str, uses: tuple[FilterUse, ...]
    ) -> None:
        """Replace the picks and nothing else; a first write creates the row on the defaults."""
        rows = [_from_use(use) for use in uses]
        await session.execute(
            insert(UserSettingsTable)
            .values(user_id=user_id, **_columns(DEFAULTS), filter_usage=rows)
            .on_conflict_do_update(index_elements=["user_id"], set_={"filter_usage": rows})
        )


def _columns(settings: AppSettings) -> dict[str, Any]:
    return asdict(settings) | {"preferred_doubles": list(settings.preferred_doubles)}


def _to_use(row: dict[str, Any]) -> FilterUse:
    return FilterUse(
        view=row["view"],
        key=row["key"],
        value=row["value"],
        score=row["score"],
        last_used_at=datetime.fromisoformat(row["last_used_at"]),
    )


def _from_use(use: FilterUse) -> dict[str, Any]:
    return {
        "view": use.view,
        "key": use.key,
        "value": use.value,
        "score": use.score,
        "last_used_at": use.last_used_at.isoformat(),
    }


repository = SettingsRepository()
