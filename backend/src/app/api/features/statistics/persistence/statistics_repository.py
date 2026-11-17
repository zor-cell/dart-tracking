"""Loads the legs a player actually threw, for the tally in `domain/`."""

import asyncio
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Row, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import (
    by_game,
    game_filter_clauses,
    hidden_by,
)
from app.api.features.game.persistence.game_settings import load_setups
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.domain.overview import StatisticsOverview
from app.api.features.statistics.domain.player_statistics import PlayerStatistics, VisitRef
from app.api.features.statistics.domain.trend import TrendPoint


# The figures are points, checkouts and busts, so the other variants stay out.
_POINTS_VARIANTS = [variant.value for variant in GameVariant if variant.counts_points]


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
    # Whether anyone else threw in the game.
    against_others: bool = False

    def add_to(self, statistics: PlayerStatistics) -> None:
        statistics.add_leg(
            self.mode, self.checkout_mode, self.turns, self.refs, self.starts, self.against_others
        )


@dataclass(frozen=True)
class _Rows:
    seats: Sequence[Row[Any]]
    setups: dict[str, GameSetup]
    turns: Sequence[TurnTable]
    darts: Sequence[DartTable]


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
        seats = [*seat_clauses(user_id, player), GameTable.id.not_in(hidden_by(user_id))]
        rows = await self._rows(session, seats, criteria, last)
        return await asyncio.to_thread(_overview, rows)

    async def _rows(
        self,
        session: AsyncSession,
        seats_of: list[ColumnElement[bool]],
        criteria: GameFilter,
        last: int | None,
    ) -> _Rows:
        """The seats of the games `criteria` selects, newest first, with their setups,
        turns and darts, in a few queries for any number of games."""
        counted = [
            *seats_of,
            GameTable.status == GameStatus.FINISHED.value,
            GameTable.variant.in_(_POINTS_VARIANTS),
            exists().where(TurnTable.game_id == GameTable.id),
            *game_filter_clauses(criteria),
        ]
        seats = (
            await session.execute(
                select(
                    GameTable.id,
                    GameTable.variant,
                    GameTable.created_at,
                    GamePlayerTable.player_index,
                )
                .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(*counted, *latest_games(counted, last))
                .order_by(GameTable.created_at.desc(), GameTable.id)
            )
        ).all()

        ids = list(dict.fromkeys(seat.id for seat in seats))
        if not ids:
            return _Rows([], {}, [], [])
        setups = await load_setups(session, {seat.id: GameVariant(seat.variant) for seat in seats})
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

        return _Rows(seats, setups, turn_rows, dart_rows)


def _overview(rows: _Rows) -> StatisticsOverview:
    """Every counted leg in one tally and game by game, oldest first."""
    totals = PlayerStatistics()
    games: dict[str, TrendPoint] = {}
    for leg in reversed(_legs(rows)):
        leg.add_to(totals)
        point = games.setdefault(
            leg.game_id, TrendPoint(leg.game_id, leg.played_at, PlayerStatistics())
        )
        leg.add_to(point.statistics)
    return StatisticsOverview(totals, list(games.values()))


def _legs(rows: _Rows) -> list[_Leg]:
    """Each seat's own turns, with the whole game replayed for where each began."""
    seats, setups, turn_rows, dart_rows = rows.seats, rows.setups, rows.turns, rows.darts
    darts: dict[tuple[str, int], list[Dart]] = {}
    for row in dart_rows:
        position = None if row.pos_x is None else (row.pos_x, row.pos_y)
        darts.setdefault((row.game_id, row.turn_index), []).append(
            Dart(value=row.value, multiplier=row.multiplier, position=position)
        )

    visit_of = visit_numbers(turn_rows, darts.keys())

    turns_of = by_game(turn_rows)
    legs: list[_Leg] = []
    for seat in seats:
        game_rows = turns_of.get(seat.id)
        if not game_rows:
            continue
        setup = setups[seat.id]
        game = Game(
            id=seat.id,
            mode=setup.mode,
            players=[
                Player(id=index, name="", identity_id="")
                for index in sorted({row.player_index for row in game_rows})
            ],
            variant=setup.variant,
            checkout_mode=setup.checkout_mode,
            options=setup.options,
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
                mode=int(game.mode or 0),
                checkout_mode=game.checkout_mode or CheckoutMode.DOUBLE_OUT,
                turns=turns,
                refs=refs,
                starts=[start for _, _, start in own],
                against_others=len(game.players) > 1,
            )
        )

    return legs


def visit_numbers(
    turn_rows: Sequence[TurnTable], with_darts: Collection[tuple[str, int]]
) -> dict[tuple[str, int], int]:
    """Each turn with darts by its place among its game's visits, as the replay counts them."""
    visit_of: dict[tuple[str, int], int] = {}
    visits_so_far: Counter[str] = Counter()
    for row in turn_rows:
        if (row.game_id, row.turn_index) in with_darts:
            visit_of[row.game_id, row.turn_index] = visits_so_far[row.game_id]
            visits_so_far[row.game_id] += 1
    return visit_of


def latest_games(
    clauses: list[ColumnElement[bool]], last: int | None
) -> list[ColumnElement[bool]]:
    """Narrows a seat query to the `last` most recent games its `clauses` select."""
    if last is None:
        return []
    latest = (
        select(GameTable.id)
        .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
        .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
        .where(*clauses)
        .group_by(GameTable.id, GameTable.created_at)
        .order_by(GameTable.created_at.desc(), GameTable.id)
        .limit(last)
    )
    return [GameTable.id.in_(latest)]


def seat_clauses(user_id: str, player: PlayerIdentity | None) -> list[ColumnElement[bool]]:
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
