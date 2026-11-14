"""Loads the darts a player threw at a named field, for the tally in `domain/`."""

from itertools import groupby

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.target import Target
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import game_filter_clauses, hidden_by
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.target_statistics import (
    AimedDart,
    TargetStatistics,
)
from app.api.features.statistics.persistence.statistics_repository import seat_clauses

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
        statistics = TargetStatistics()
        await self._fill(session, statistics, user_id, criteria, last, player, None)
        return statistics

    async def _fill(
        self,
        session: AsyncSession,
        statistics: TargetStatistics,
        user_id: str,
        criteria: GameFilter,
        last: int | None,
        player: PlayerIdentity | None,
        target: Target | None,
    ) -> None:
        aimed_at = [DartTable.target_value.is_not(None)]
        if target is not None:
            ring = DartTable.target_multiplier
            aimed_at = [
                DartTable.target_value == target.value,
                ring.is_(None) if target.multiplier is None else ring == target.multiplier,
            ]
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
                    *seat_clauses(user_id, player),
                    GameTable.id.not_in(hidden_by(user_id)),
                    GameTable.status == GameStatus.FINISHED.value,
                    *aimed_at,
                    *game_filter_clauses(criteria),
                )
                .order_by(
                    GameTable.created_at.desc(),
                    GameTable.id,
                    DartTable.turn_index,
                    DartTable.dart_index,
                )
            )
        ).all()

        games = [list(darts) for _, darts in groupby(rows, key=lambda row: row.id)]
        for darts in reversed(games[:last]):
            aimed = [_aimed(row.DartTable) for row in darts]
            through = darts[0].variant == GameVariant.AROUND_THE_CLOCK.value and any(
                dart.target.value == _BULL and dart.hit for dart in aimed
            )
            statistics.add_game(darts[0].id, darts[0].created_at, aimed, through)


def _aimed(row: DartTable) -> AimedDart:
    position = None if row.pos_x is None or row.pos_y is None else (row.pos_x, row.pos_y)
    return AimedDart(
        Target(row.target_value or 0, row.target_multiplier),
        Dart(value=row.value, multiplier=row.multiplier, position=position),
    )


repository = TargetRepository()
