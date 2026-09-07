"""Reads and writes the tracking event log."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.evaluation.domain.tracking_event import (
    TrackingEvent,
    TrackingEventKind,
)
from app.api.features.evaluation.persistence.tracking_event import TrackingEventTable
from app.api.features.game.persistence.game import GameTable


class EvaluationRepository:
    def append(self, session: AsyncSession, game_id: str, event: TrackingEvent) -> None:
        """Queue one event. Flushed with the transaction it was recorded in, so
        an event and the state change it describes commit together."""
        session.add(
            TrackingEventTable(
                game_id=game_id,
                kind=event.kind.value,
                turn_index=event.turn_index,
                player_index=event.player_index,
                accepted=event.accepted,
                camera_armed=event.camera_armed,
                client_id=event.client_id,
                value=event.value,
                multiplier=event.multiplier,
                pos_x=event.position[0] if event.position else None,
                pos_y=event.position[1] if event.position else None,
                failure=event.failure,
                metrics=event.metrics,
            )
        )

    async def events(self, session: AsyncSession, game_id: str) -> list[TrackingEvent]:
        """The whole log of one game, in the order it was written."""
        try:
            UUID(game_id)
        except ValueError:
            return []

        rows = (
            await session.execute(
                select(TrackingEventTable)
                .where(TrackingEventTable.game_id == game_id)
                .order_by(TrackingEventTable.id)
            )
        ).scalars().all()

        return [
            TrackingEvent(
                kind=TrackingEventKind(row.kind),
                turn_index=row.turn_index,
                player_index=row.player_index,
                accepted=row.accepted,
                camera_armed=row.camera_armed,
                client_id=row.client_id,
                value=row.value,
                multiplier=row.multiplier,
                position=None if row.pos_x is None else (row.pos_x, row.pos_y),
                failure=row.failure,
                metrics=row.metrics,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def logged_games(
        self, session: AsyncSession, *, evaluation_only: bool
    ) -> list[str]:
        """Games that have a log, oldest first. `evaluation_only` narrows it to
        the ones marked as a test run."""
        # `created_at` is selected as well as ordered on: Postgres rejects a
        # DISTINCT whose ORDER BY names a column that is not in the list.
        statement = (
            select(GameTable.id, GameTable.created_at)
            .join(TrackingEventTable, TrackingEventTable.game_id == GameTable.id)
            .order_by(GameTable.created_at)
            .distinct()
        )
        if evaluation_only:
            statement = statement.where(GameTable.evaluation_enabled.is_(True))
        return [row.id for row in (await session.execute(statement)).all()]


repository = EvaluationRepository()
