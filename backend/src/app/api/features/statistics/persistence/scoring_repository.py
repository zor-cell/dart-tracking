"""Loads the visits of the trainings without a target, for the tally in `domain/`."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import ColumnElement, Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.training import TrainingGoal
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import (
    by_game,
    game_filter_clauses,
    hidden_by,
)
from app.api.features.game.persistence.training_settings import TrainingSettingsTable
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.player_statistics import VisitRef
from app.api.features.statistics.domain.scoring_statistics import ScoringStatistics
from app.api.features.statistics.persistence.statistics_repository import (
    latest_games,
    seat_clauses,
    visit_numbers,
)


@dataclass(frozen=True)
class _Rows:
    seats: Sequence[Row[Any]]
    turns: Sequence[TurnTable]
    darts: Sequence[DartTable]


class ScoringRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> ScoringStatistics:
        """The finished trainings without a target that `criteria` selects; `last` keeps
        those among the most recent trainings of any goal."""
        if not _selects_free(criteria):
            return ScoringStatistics()
        rows = await self._rows(session, user_id, criteria, last, player)
        return await asyncio.to_thread(_tally, rows)

    async def _rows(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter,
        last: int | None,
        player: PlayerIdentity | None,
    ) -> _Rows:
        trainings = [
            *seat_clauses(user_id, player),
            GameTable.id.not_in(hidden_by(user_id)),
            GameTable.status == GameStatus.FINISHED.value,
            GameTable.variant == GameVariant.TRAINING.value,
            *game_filter_clauses(replace(criteria, training_goals=())),
        ]
        free: ColumnElement[bool] = GameTable.id.in_(
            select(TrainingSettingsTable.game_id).where(
                TrainingSettingsTable.goal == TrainingGoal.FREE.value
            )
        )
        seats = (
            await session.execute(
                select(GameTable.id, GameTable.created_at, GamePlayerTable.player_index)
                .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(*trainings, free, *latest_games(trainings, last))
                .order_by(GameTable.created_at.desc(), GameTable.id)
            )
        ).all()
        ids = list(dict.fromkeys(seat.id for seat in seats))
        if not ids:
            return _Rows([], [], [])
        turns = (
            await session.execute(
                select(TurnTable)
                .where(TurnTable.game_id.in_(ids))
                .order_by(TurnTable.game_id, TurnTable.turn_index)
            )
        ).scalars().all()
        darts = (
            await session.execute(
                select(DartTable)
                .where(DartTable.game_id.in_(ids))
                .order_by(DartTable.game_id, DartTable.turn_index, DartTable.dart_index)
            )
        ).scalars().all()
        return _Rows(seats, turns, darts)


def _selects_free(criteria: GameFilter) -> bool:
    """Whether the filters leave room for a training without a target, which has no ring."""
    return (
        (not criteria.variants or GameVariant.TRAINING in criteria.variants)
        and (not criteria.training_goals or TrainingGoal.FREE in criteria.training_goals)
        and not criteria.training_rings
    )


def _tally(rows: _Rows) -> ScoringStatistics:
    """Each seat's own visits, oldest game first."""
    darts: dict[tuple[str, int], list[Dart]] = {}
    for row in rows.darts:
        position = None if row.pos_x is None or row.pos_y is None else (row.pos_x, row.pos_y)
        darts.setdefault((row.game_id, row.turn_index), []).append(
            Dart(value=row.value, multiplier=row.multiplier, position=position)
        )
    visit_of = visit_numbers(rows.turns, darts.keys())
    turns_of = by_game(rows.turns)

    statistics = ScoringStatistics()
    for seat in reversed(rows.seats):
        own = [row for row in turns_of.get(seat.id, []) if row.player_index == seat.player_index]
        statistics.add_game(
            seat.id,
            seat.created_at,
            [
                Turn(player_id=row.player_index, darts=darts.get((row.game_id, row.turn_index), []))
                for row in own
            ],
            [
                None
                if (visit := visit_of.get((row.game_id, row.turn_index))) is None
                else VisitRef(seat.id, visit, seat.created_at)
                for row in own
            ],
        )
    return statistics


repository = ScoringRepository()
