"""Reads and writes the game event log."""

from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.evaluation.domain.accuracy import LoggedGame
from app.api.features.evaluation.domain.game_event import (
    GameEvent,
    GameEventKind,
)
from app.api.features.evaluation.persistence.game_event import GameEventTable
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_repository import by_game
from app.api.features.game.persistence.game_settings import start_score


class EvaluationRepository:
    def append(self, session: AsyncSession, game_id: str, event: GameEvent) -> None:
        """Queue one event. Flushed with the transaction it was recorded in, so
        an event and the state change it describes commit together."""
        session.add(
            GameEventTable(
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
                dart_index=event.dart_index,
                target_index=event.target_index,
                failure=event.failure,
                metrics=event.metrics,
                tracker_version=event.tracker_version,
            )
        )

    async def events(
        self, session: AsyncSession, game_ids: list[str]
    ) -> dict[str, list[GameEvent]]:
        """The whole log of each of these games, in the order it was written."""
        if not game_ids:
            return {}
        rows = (
            await session.execute(
                select(GameEventTable)
                .where(GameEventTable.game_id.in_(game_ids))
                .order_by(GameEventTable.id)
            )
        ).scalars().all()
        return {game_id: events_from_rows(of_game) for game_id, of_game in by_game(rows).items()}

    async def logged_games(
        self,
        session: AsyncSession,
        *,
        evaluation_only: bool,
        finished_only: bool = False,
        game_ids: list[str] | None = None,
    ) -> list[LoggedGame]:
        """Games that have a log, oldest first. `evaluation_only` narrows it to
        the ones marked as a test run, `finished_only` to the ones with a winner,
        `game_ids` to these games."""
        versions = func.array_agg(distinct(GameEventTable.tracker_version)).filter(
            GameEventTable.tracker_version.is_not(None)
        )
        statement = (
            select(
                GameTable.id,
                start_score().label("mode"),
                GameTable.created_at,
                GameTable.evaluation_enabled,
                versions.label("tracker_versions"),
            )
            .join(GameEventTable, GameEventTable.game_id == GameTable.id)
            .group_by(GameTable.id)
            .order_by(GameTable.created_at)
        )
        if evaluation_only:
            statement = statement.where(GameTable.evaluation_enabled.is_(True))
        if finished_only:
            statement = statement.where(GameTable.status == GameStatus.FINISHED.value)
        if game_ids is not None:
            statement = statement.where(GameTable.id.in_([id for id in game_ids if _is_uuid(id)]))

        return [
            LoggedGame(
                id=row.id,
                mode=row.mode,
                created_at=row.created_at,
                evaluation_enabled=row.evaluation_enabled,
                tracker_versions=tuple(sorted(row.tracker_versions or ())),
            )
            for row in (await session.execute(statement)).all()
        ]


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def events_from_rows(rows: list[GameEventTable]) -> list[GameEvent]:
    return [
        GameEvent(
            kind=GameEventKind(row.kind),
            turn_index=row.turn_index,
            player_index=row.player_index,
            accepted=row.accepted,
            camera_armed=row.camera_armed,
            client_id=row.client_id,
            value=row.value,
            multiplier=row.multiplier,
            position=None if row.pos_x is None else (row.pos_x, row.pos_y),
            dart_index=row.dart_index,
            target_index=row.target_index,
            failure=row.failure,
            metrics=row.metrics,
            tracker_version=row.tracker_version,
            created_at=row.created_at,
        )
        for row in rows
    ]


repository = EvaluationRepository()
