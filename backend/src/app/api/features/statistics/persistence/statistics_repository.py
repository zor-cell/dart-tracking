"""Loads the legs a player actually threw, for the tally in `domain/`."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import game_filter_clauses, hidden_by
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.overview import StatisticsOverview
from app.api.features.statistics.domain.player_statistics import PlayerStatistics, VisitRef
from app.api.features.statistics.domain.trend import TrendPoint


@dataclass(frozen=True)
class _Leg:
    """One counted seat: the player's own turns with where and from what each began."""

    game_id: str
    played_at: datetime
    mode: int
    checkout_mode: CheckoutMode
    turns: list[Turn]
    refs: list[VisitRef | None]
    starts: list[int]

    def add_to(self, statistics: PlayerStatistics) -> None:
        statistics.add_leg(self.mode, self.checkout_mode, self.turns, self.refs, self.starts)


class StatisticsRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> StatisticsOverview:
        """Every counted leg of the games `criteria` selects, in one tally and game by game;
        `last` keeps only the most recent games that count, `player` reads that one instead."""
        seats = [*_seats(user_id, player), GameTable.id.not_in(hidden_by(user_id))]
        legs = await self._legs(session, seats, criteria, last)
        totals = PlayerStatistics()
        games: dict[str, TrendPoint] = {}
        for leg in reversed(legs):
            leg.add_to(totals)
            point = games.setdefault(
                leg.game_id, TrendPoint(leg.game_id, leg.played_at, PlayerStatistics())
            )
            leg.add_to(point.statistics)
        return StatisticsOverview(totals, list(games.values()))

    async def _legs(
        self,
        session: AsyncSession,
        seats_of: list[ColumnElement[bool]],
        criteria: GameFilter,
        last: int | None,
    ) -> list[_Leg]:
        """Three queries for the games `criteria` selects, not four per game: the
        seats, their turns, their darts — then the rules run in Python. Newest first."""
        seats = (
            await session.execute(
                select(
                    GameTable.id,
                    GameTable.mode,
                    GameTable.variant,
                    GameTable.checkout_mode,
                    GameTable.created_at,
                    GamePlayerTable.player_index,
                )
                .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(
                    *seats_of,
                    GameTable.status == GameStatus.FINISHED.value,
                    *game_filter_clauses(criteria),
                )
                .order_by(GameTable.created_at.desc(), GameTable.id)
            )
        ).all()

        if not seats:
            return []

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

        # Each turn with darts by its place among its game's visits, as the replay counts them.
        visit_of: dict[tuple[str, int], int] = {}
        visits_so_far: Counter[str] = Counter()
        for row in turn_rows:
            if (row.game_id, row.turn_index) in darts:
                visit_of[row.game_id, row.turn_index] = visits_so_far[row.game_id]
                visits_so_far[row.game_id] += 1

        legs: list[_Leg] = []
        counted: set[str] = set()
        for seat in seats:
            game_rows = [row for row in turn_rows if row.game_id == seat.id]
            if not game_rows:
                continue
            game = Game(
                id=seat.id,
                mode=GameMode(seat.mode),
                players=[
                    Player(id=index, name="", identity_id="")
                    for index in sorted({row.player_index for row in game_rows})
                ],
                variant=GameVariant(seat.variant),
                checkout_mode=CheckoutMode(seat.checkout_mode),
                turns=[
                    Turn(
                        player_id=row.player_index,
                        darts=darts.get((row.game_id, row.turn_index), []),
                        busted=row.busted,
                    )
                    for row in game_rows
                ],
            )
            # The whole game is replayed, since in elimination the others reset your score.
            own = [
                (row, turn, start)
                for row, turn, start in zip(
                    game_rows, game.turns, game.remaining_before_turns(), strict=True
                )
                if row.player_index == seat.player_index
            ]
            turns = [turn for _, turn, _ in own]
            if last is not None and seat.id not in counted and len(counted) == last:
                break
            counted.add(seat.id)

            refs = [
                None
                if (visit := visit_of.get((row.game_id, row.turn_index))) is None
                else VisitRef(seat.id, visit, seat.created_at)
                for row, _, _ in own
            ]
            legs.append(
                _Leg(
                    game_id=seat.id,
                    played_at=seat.created_at,
                    mode=seat.mode,
                    checkout_mode=CheckoutMode(seat.checkout_mode),
                    turns=turns,
                    refs=refs,
                    starts=[start for _, _, start in own],
                )
            )

        return legs


def _seats(user_id: str, player: PlayerIdentity | None) -> list[ColumnElement[bool]]:
    """The account's own seats, or those of `player` in the games the account set up
    or sat in; a linked entry counts every seat of its account."""
    if player is None:
        return [PlayerTable.user_id == user_id]
    seated = (
        select(GamePlayerTable.game_id)
        .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
        .where(PlayerTable.user_id == user_id)
    )
    whose = (
        PlayerTable.id == player.id
        if player.user_id is None
        else PlayerTable.user_id == player.user_id
    )
    return [whose, or_(GameTable.owner_user_id == user_id, GameTable.id.in_(seated))]


repository = StatisticsRepository()
