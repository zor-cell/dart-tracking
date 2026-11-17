"""Loads the darts a player threw at a named field, for the tally in `domain/`."""

import asyncio
from collections.abc import Sequence
from itertools import groupby
from typing import Any

from sqlalchemy import Row, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.target import Target
from app.api.features.game.domain.training import TrainingGoal
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import game_filter_clauses, hidden_by
from app.api.features.game.persistence.training_settings import TrainingSettingsTable
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.target_statistics import (
    AimedDart,
    TargetStatistics,
)
from app.api.features.statistics.persistence.statistics_repository import (
    latest_games,
    seat_clauses,
)

_BULL = 25


class TargetRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> TargetStatistics:
        """The aimed darts of the finished games `criteria` selects; `last` keeps the
        most recent games with any, `player` reads that one instead of the account."""
        seats = [
            *seat_clauses(user_id, player),
            GameTable.id.not_in(hidden_by(user_id)),
            GameTable.status == GameStatus.FINISHED.value,
            *game_filter_clauses(criteria),
        ]
        aimed_by_seat = (
            exists()
            .where(
                DartTable.game_id == GameTable.id,
                DartTable.target_value.is_not(None),
                TurnTable.game_id == DartTable.game_id,
                TurnTable.turn_index == DartTable.turn_index,
                TurnTable.player_index == GamePlayerTable.player_index,
            )
            .correlate(GameTable, GamePlayerTable)
        )
        # A training without a target takes its place among the last games too.
        free_training = GameTable.id.in_(
            select(TrainingSettingsTable.game_id).where(
                TrainingSettingsTable.goal == TrainingGoal.FREE.value
            )
        )
        rows = (
            await session.execute(
                select(GameTable.id, GameTable.created_at, GameTable.variant, DartTable)
                .join(
                    TurnTable,
                    (TurnTable.game_id == DartTable.game_id)
                    & (TurnTable.turn_index == DartTable.turn_index),
                )
                .join(GameTable, GameTable.id == DartTable.game_id)
                .join(
                    GamePlayerTable,
                    (GamePlayerTable.game_id == TurnTable.game_id)
                    & (GamePlayerTable.player_index == TurnTable.player_index),
                )
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(
                    *seats,
                    DartTable.target_value.is_not(None),
                    *latest_games([*seats, or_(aimed_by_seat, free_training)], last),
                )
                .order_by(
                    GameTable.created_at.desc(),
                    GameTable.id,
                    DartTable.turn_index,
                    DartTable.dart_index,
                )
            )
        ).all()

        return await asyncio.to_thread(_tally, rows)


def _tally(rows: Sequence[Row[Any]]) -> TargetStatistics:
    """The rows' aimed darts game by game, oldest first."""
    statistics = TargetStatistics()
    games = [list(darts) for _, darts in groupby(rows, key=lambda row: row.id)]
    for darts in reversed(games):
        aimed = [_aimed(row.DartTable) for row in darts]
        through = darts[0].variant == GameVariant.AROUND_THE_CLOCK.value and any(
            dart.target.value == _BULL and dart.hit for dart in aimed
        )
        statistics.add_game(darts[0].id, darts[0].created_at, aimed, through)
    return statistics


def _aimed(row: DartTable) -> AimedDart:
    position = None if row.pos_x is None or row.pos_y is None else (row.pos_x, row.pos_y)
    return AimedDart(
        Target(row.target_value or 0, row.target_multiplier),
        Dart(value=row.value, multiplier=row.multiplier, position=position),
    )


repository = TargetRepository()
