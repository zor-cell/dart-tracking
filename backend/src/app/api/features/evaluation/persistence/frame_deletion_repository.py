"""Queues the kept frames of games for deletion and hands the queue to the sweeper."""

from datetime import datetime

from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.evaluation.persistence.frame_deletion import FrameDeletionTable
from app.api.features.game.persistence.game import GameTable


class FrameDeletionRepository:
    async def stop_keeping(self, session: AsyncSession, condition: ColumnElement[bool]) -> None:
        """Turn frame keeping off for the matching games and queue what they kept."""
        kept = _kept(condition)
        await session.execute(
            upsert(FrameDeletionTable)
            .from_select(["game_id"], select(GameTable.id).where(kept))
            .on_conflict_do_nothing()
        )
        await session.execute(update(GameTable).where(kept).values(evaluation_enabled=False))

    async def stop_keeping_owned(self, session: AsyncSession, user_id: str) -> None:
        await self.stop_keeping(session, GameTable.owner_user_id == user_id)

    async def stop_keeping_game(self, session: AsyncSession, game_id: str) -> None:
        """Queue one game's frames, whatever its switch says now."""
        await session.execute(
            upsert(FrameDeletionTable).values(game_id=game_id).on_conflict_do_nothing()
        )

    async def expire(self, session: AsyncSession, before: datetime) -> None:
        """Queue the frames of every game set up before `before`."""
        await self.stop_keeping(session, GameTable.created_at < before)

    async def pending(self, session: AsyncSession, limit: int = 100) -> list[str]:
        rows = await session.execute(
            select(FrameDeletionTable.game_id).order_by(FrameDeletionTable.requested_at).limit(limit)
        )
        return list(rows.scalars())

    async def done(self, session: AsyncSession, game_ids: list[str]) -> None:
        if game_ids:
            await session.execute(
                delete(FrameDeletionTable).where(FrameDeletionTable.game_id.in_(game_ids))
            )


def _kept(condition: ColumnElement[bool]) -> ColumnElement[bool]:
    return GameTable.evaluation_enabled.is_(True) & condition


repository = FrameDeletionRepository()
