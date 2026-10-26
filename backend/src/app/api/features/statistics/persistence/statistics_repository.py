"""Loads the legs a player actually threw, for the tally in `domain/`."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_status import (
    ABANDON_AFTER,
    GameStatus,
    counts_in_statistics,
    effective_status,
)
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import game_filter_clauses
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.player_statistics import PlayerStatistics


class StatisticsRepository:
    async def tally(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
    ) -> PlayerStatistics:
        """Three queries for the games `criteria` selects, not four per game: the
        seats, their turns, their darts — then the rules run in Python. `last`
        keeps only the most recent games that count."""
        cutoff = datetime.now(UTC) - ABANDON_AFTER
        seats = (
            await session.execute(
                select(
                    GameTable.id,
                    GameTable.mode,
                    GameTable.variant,
                    GameTable.checkout_mode,
                    GameTable.status,
                    GameTable.updated_at,
                    GamePlayerTable.player_index,
                )
                .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(
                    PlayerTable.user_id == user_id,
                    or_(
                        GameTable.status == GameStatus.FINISHED.value,
                        (GameTable.status == GameStatus.ACTIVE.value)
                        & (GameTable.updated_at < cutoff),
                    ),
                    *game_filter_clauses(criteria),
                )
                .order_by(GameTable.created_at.desc(), GameTable.id)
            )
        ).all()

        statistics = PlayerStatistics()
        if not seats:
            return statistics

        ids = [seat.id for seat in seats]
        turn_rows = (
            await session.execute(
                select(TurnTable)
                .where(TurnTable.game_id.in_(ids))
                .order_by(TurnTable.game_id, TurnTable.turn_index)
            )
        ).scalars().all()
        dart_rows = (
            await session.execute(
                select(DartTable)
                .where(DartTable.game_id.in_(ids))
                .order_by(DartTable.game_id, DartTable.turn_index, DartTable.dart_index)
            )
        ).scalars().all()

        darts: dict[tuple[str, int], list[Dart]] = {}
        for row in dart_rows:
            position = None if row.pos_x is None else (row.pos_x, row.pos_y)
            darts.setdefault((row.game_id, row.turn_index), []).append(
                Dart(value=row.value, multiplier=row.multiplier, position=position)
            )

        counted: set[str] = set()
        for seat in seats:
            turns = [
                Turn(
                    player_id=row.player_index,
                    darts=darts.get((row.game_id, row.turn_index), []),
                    busted=row.busted,
                )
                for row in turn_rows
                if row.game_id == seat.id and row.player_index == seat.player_index
            ]
            own_darts = sum(len(turn.darts) for turn in turns)
            status = effective_status(GameStatus(seat.status), seat.updated_at)
            if not counts_in_statistics(status, own_darts):
                continue

            # Elimination legs are left out: the countdown below cannot see the
            # resets other players caused, so every rate it derives would be wrong.
            if GameVariant(seat.variant) is not GameVariant.X01:
                continue

            if last is not None and seat.id not in counted and len(counted) == last:
                break
            counted.add(seat.id)

            statistics.add_leg(seat.mode, CheckoutMode(seat.checkout_mode), turns)

        return statistics


repository = StatisticsRepository()
