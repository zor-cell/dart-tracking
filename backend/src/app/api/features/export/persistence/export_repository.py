"""Reads everything an account holds in a fixed number of queries, whatever its size."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.auth.domain.user import User
from app.api.features.evaluation.domain.game_event import GameEvent
from app.api.features.evaluation.persistence.evaluation_repository import (
    repository as evaluation_repository,
)
from app.api.features.export.domain.account_export import (
    AccountExport,
    ExportedDart,
    ExportedGame,
    ExportedSeat,
    ExportedTurn,
)
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_status import GameStatus, effective_status
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.target import Target
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import by_game, hidden_by, involving
from app.api.features.game.persistence.game_settings import load_setups
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable, shown_name
from app.api.features.settings.domain.app_settings import AppSettings
from app.api.features.settings.domain.filter_use import FilterUse
from app.api.features.settings.persistence.settings_repository import (
    repository as settings_repository,
)


@dataclass(frozen=True)
class ExportRows:
    """The loaded rows, turned into the domain by `assemble` off the event loop."""

    user: User
    settings: AppSettings
    filter_usage: tuple[FilterUse, ...]
    players: Sequence[PlayerTable]
    games: Sequence[GameTable]
    setups: dict[str, GameSetup]
    hidden: set[str]
    seats: Sequence[Any]
    turns: Sequence[TurnTable]
    darts: Sequence[DartTable]
    events: dict[str, list[GameEvent]]


class ExportRepository:
    async def load(self, session: AsyncSession, user: User) -> ExportRows:
        players = (
            await session.execute(
                select(PlayerTable)
                .where(or_(PlayerTable.owner_user_id == user.id, PlayerTable.user_id == user.id))
                .order_by(PlayerTable.created_at, PlayerTable.id)
            )
        ).scalars().all()
        games = (
            await session.execute(
                select(GameTable).where(involving(user.id)).order_by(GameTable.created_at)
            )
        ).scalars().all()
        ids = [game.id for game in games]
        owned = [game.id for game in games if game.owner_user_id == user.id]
        seats = (
            await session.execute(
                select(
                    GamePlayerTable.game_id,
                    GamePlayerTable.player_index,
                    GamePlayerTable.player_id,
                    PlayerTable.display_name,
                    PlayerTable.user_id,
                )
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(GamePlayerTable.game_id.in_(ids))
                .order_by(GamePlayerTable.game_id, GamePlayerTable.player_index)
            )
        ).all()
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
        hidden = set((await session.execute(hidden_by(user.id))).scalars().all())
        return ExportRows(
            user=user,
            settings=await settings_repository.get(session, user.id),
            filter_usage=await settings_repository.filter_usage(session, user.id),
            players=players,
            games=games,
            setups=await load_setups(session, {game.id: GameVariant(game.variant) for game in games}),
            hidden=hidden,
            seats=seats,
            turns=turns,
            darts=darts,
            events=await evaluation_repository.events(session, owned),
        )


def assemble(rows: ExportRows) -> AccountExport:
    """The export from its rows."""
    seats_of, turns_of, darts_of = by_game(rows.seats), by_game(rows.turns), by_game(rows.darts)
    return AccountExport(
        user=rows.user,
        settings=rows.settings,
        filter_usage=rows.filter_usage,
        players=tuple(
            PlayerIdentity(id=row.id, display_name=shown_name(row.display_name), user_id=row.user_id)
            for row in rows.players
        ),
        games=tuple(
            _game(
                row,
                rows,
                seats_of.get(row.id, []),
                turns_of.get(row.id, []),
                darts_of.get(row.id, []),
            )
            for row in rows.games
        ),
    )


def _game(
    row: GameTable,
    rows: ExportRows,
    seats: Sequence[Any],
    turns: Sequence[TurnTable],
    darts: Sequence[DartTable],
) -> ExportedGame:
    darts_of: dict[int, list[ExportedDart]] = {}
    for dart in darts:
        darts_of.setdefault(dart.turn_index, []).append(_dart(dart))
    return ExportedGame(
        id=row.id,
        setup=rows.setups[row.id],
        status=effective_status(GameStatus(row.status), row.updated_at),
        hidden=row.id in rows.hidden,
        owned=row.owner_user_id == rows.user.id,
        evaluation_enabled=row.evaluation_enabled,
        created_at=row.created_at,
        finished_at=row.finished_at,
        seats=tuple(
            ExportedSeat(
                player_id=seat.player_id,
                name=shown_name(seat.display_name),
                is_me=seat.user_id == rows.user.id,
            )
            for seat in seats
        ),
        turns=tuple(
            ExportedTurn(
                player_index=turn.player_index,
                busted=turn.busted,
                ended_at=turn.ended_at,
                darts=tuple(darts_of.get(turn.turn_index, [])),
            )
            for turn in turns
        ),
        events=tuple(rows.events.get(row.id, [])),
    )


def _dart(row: DartTable) -> ExportedDart:
    position = None if row.pos_x is None or row.pos_y is None else (row.pos_x, row.pos_y)
    target = None if row.target_value is None else Target(row.target_value, row.target_multiplier)
    return ExportedDart(
        dart=Dart(
            value=row.value,
            multiplier=row.multiplier,
            position=position,
            thrown_at=row.thrown_at,
        ),
        target=target,
    )


repository = ExportRepository()
