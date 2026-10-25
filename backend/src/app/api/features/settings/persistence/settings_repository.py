"""Reads and writes an account's settings."""

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.settings.domain.app_settings import DEFAULTS, AppSettings
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
            confirm_throw_enabled=row.confirm_throw_enabled,
            evaluation_enabled=row.evaluation_enabled,
            debug_calibration=row.debug_calibration,
            debug_detection=row.debug_detection,
            preferred_doubles=tuple(row.preferred_doubles),
        )

    async def save(
        self, session: AsyncSession, user_id: str, settings: AppSettings
    ) -> None:
        """Write the whole set. Upsert rather than read-then-write: the first
        change an account makes is also the row's insert."""
        values = asdict(settings) | {"preferred_doubles": list(settings.preferred_doubles)}
        await session.execute(
            insert(UserSettingsTable)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=["user_id"], set_={**values, "updated_at": func.now()}
            )
        )


repository = SettingsRepository()
