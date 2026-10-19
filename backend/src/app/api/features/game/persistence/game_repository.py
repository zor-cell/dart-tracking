"""Loads and stores the game aggregate.

The server is the source of truth for every score, so a game is read fresh for
each command and written back inside the same transaction.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, and_, case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_record import GameRecord
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import (
    ABANDON_AFTER,
    GameStatus,
    effective_status,
    is_resumable,
)
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.game_summary import GameSummary, GameSummaryPlayer
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.settings.persistence.user_settings import UserSettingsTable

# Games carry a foreign key to `users`, so that table has to be registered too.
from app.api import tables  # noqa: F401


class GameRepository:
    async def create(
        self,
        session: AsyncSession,
        mode: GameMode,
        identities: list[PlayerIdentity],
        variant: GameVariant,
        checkout_mode: CheckoutMode,
        owner_user_id: str | None = None,
        evaluation_enabled: bool = False,
    ) -> Game:
        """The identities are resolved by the router, which owns the rules about
        who may take a seat. Here they are only seated, in the order given."""
        # The id is only known after the flush below — Postgres generates it.
        game = Game(
            id="",
            mode=mode,
            variant=variant,
            players=[
                Player(id=seat, name=identity.display_name, identity_id=identity.id)
                for seat, identity in enumerate(identities)
            ],
            checkout_mode=checkout_mode,
            evaluation_enabled=evaluation_enabled,
        )

        row = GameTable(
            mode=int(mode),
            variant=variant.value,
            checkout_mode=checkout_mode.value,
            status=GameStatus.ACTIVE.value,
            current_player_index=game.current_player_index,
            revision=game.revision,
            evaluation_enabled=evaluation_enabled,
            owner_user_id=owner_user_id,
        )
        session.add(row)
        # Flush before adding `game_players`: no relationships are declared, so
        # the unit of work does not order the inserts by foreign key on its own.
        # It is also where the server-side id arrives.
        await session.flush()

        session.add_all(
            GamePlayerTable(game_id=row.id, player_index=index, player_id=identity.id)
            for index, identity in enumerate(identities)
        )
        await session.flush()

        game.id = row.id
        await self.save(session, game)
        preferred = await self._preferred_doubles(session, [i.id for i in identities])
        for player in game.players:
            player.preferred_doubles = preferred.get(player.identity_id, ())
        return game

    async def get(self, session: AsyncSession, game_id: str) -> Game | None:
        """Read without locking — for the endpoints that only display a game."""
        return await self._load(session, game_id, lock=False)

    async def record_for(
        self, session: AsyncSession, game_id: str, user_id: str
    ) -> GameRecord | None:
        """The game's record, or None unless this account set it up or holds a seat in it."""
        try:
            UUID(game_id)
        except ValueError:
            return None

        seated = (
            select(GamePlayerTable.game_id)
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .where(GamePlayerTable.game_id == game_id, PlayerTable.user_id == user_id)
        )
        row = (
            await session.execute(
                select(GameTable).where(
                    GameTable.id == game_id,
                    or_(GameTable.owner_user_id == user_id, GameTable.id.in_(seated)),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return GameRecord(
            status=effective_status(GameStatus(row.status), row.updated_at),
            created_at=row.created_at,
            finished_at=row.finished_at,
        )

    async def lock(self, session: AsyncSession, game_id: str) -> Game | None:
        """Read for a command. `SELECT … FOR UPDATE` holds the row until the
        transaction ends, so two devices ending the same visit are serialised
        rather than both finding it open."""
        return await self._load(session, game_id, lock=True)

    async def save(self, session: AsyncSession, game: Game) -> None:
        """Write the game back.

        Turns and darts are rewritten wholesale rather than diffed: a game holds
        roughly 25 turns and 70 darts, and the delete cascades, so the simple
        form costs a few milliseconds and has no edge cases around undo.
        """
        finished = game.winner is not None
        derived = (GameStatus.FINISHED if finished else GameStatus.ACTIVE).value
        game.updated_at = await session.scalar(
            update(GameTable)
            .where(GameTable.id == game.id)
            .values(
                current_player_index=game.current_player_index,
                revision=game.revision,
                evaluation_enabled=game.evaluation_enabled,
                shadow_darts=[_dart_json(dart) for dart in game.shadow_darts],
                # `discarded` is a judgement about the game, not a consequence of
                # the score, so deriving the status must not overwrite it.
                status=case(
                    (GameTable.status == GameStatus.DISCARDED.value, GameTable.status),
                    else_=derived,
                ),
                finished_at=func.now() if finished else None,
                updated_at=func.now(),
            )
            .returning(GameTable.updated_at)
        )

        # The delete cascades to this game's darts.
        await session.execute(delete(TurnTable).where(TurnTable.game_id == game.id))

        session.add_all(
            TurnTable(
                game_id=game.id,
                turn_index=turn_index,
                player_index=turn.player_id,
                busted=turn.busted,
            )
            for turn_index, turn in enumerate(game.turns)
        )
        # Turns before darts, for the reason given in `create`.
        await session.flush()

        session.add_all(
            DartTable(
                game_id=game.id,
                turn_index=turn_index,
                dart_index=dart_index,
                value=dart.value,
                multiplier=dart.multiplier,
                pos_x=dart.position[0] if dart.position else None,
                pos_y=dart.position[1] if dart.position else None,
            )
            for turn_index, turn in enumerate(game.turns)
            for dart_index, dart in enumerate(turn.darts)
        )
        await session.flush()


    async def summaries(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        limit: int,
        offset: int,
        criteria: GameFilter = GameFilter(),
    ) -> list[GameSummary]:
        """The games this account took part in or wrote down, newest first.

        Both branches are needed: a game set up by a fellow player belongs in my
        history too, and one I only kept score for has no seat for me at all.
        """
        rows = (
            await session.execute(
                select(GameTable)
                .where(*_history_clauses(user_id, criteria))
                .order_by(GameTable.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        if not rows:
            return []

        ids = [row.id for row in rows]
        seats = (
            await session.execute(
                select(
                    GamePlayerTable.game_id,
                    GamePlayerTable.player_index,
                    PlayerTable.display_name,
                    PlayerTable.user_id,
                    GamePlayerTable.player_id,
                )
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(GamePlayerTable.game_id.in_(ids))
                .order_by(GamePlayerTable.game_id, GamePlayerTable.player_index)
            )
        ).all()

        # Points and darts per seat in one aggregate: the score is what the
        # busted flag lets through, the dart count is every dart thrown.
        tallies = (
            await session.execute(
                select(
                    TurnTable.game_id,
                    TurnTable.player_index,
                    func.count(DartTable.dart_index).label("darts"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    TurnTable.busted.is_(False),
                                    DartTable.value * DartTable.multiplier,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("scored"),
                )
                .join(
                    DartTable,
                    (DartTable.game_id == TurnTable.game_id)
                    & (DartTable.turn_index == TurnTable.turn_index),
                )
                .where(TurnTable.game_id.in_(ids))
                .group_by(TurnTable.game_id, TurnTable.player_index)
            )
        ).all()

        scored = {(t.game_id, t.player_index): t.scored for t in tallies}
        thrown = {(t.game_id, t.player_index): t.darts for t in tallies}
        replayed = await self._elimination_remaining(session, rows, seats)

        summaries: list[GameSummary] = []
        for row in rows:
            entries = [seat for seat in seats if seat.game_id == row.id]
            players = [
                GameSummaryPlayer(
                    name=seat.display_name,
                    remaining=replayed.get(
                        (row.id, seat.player_index),
                        row.mode - scored.get((row.id, seat.player_index), 0),
                    ),
                    is_me=seat.user_id == user_id,
                )
                for seat in entries
            ]
            own = next(
                (
                    thrown.get((row.id, seat.player_index), 0)
                    for seat in entries
                    if seat.user_id == user_id
                ),
                0,
            )
            summaries.append(
                GameSummary(
                    id=row.id,
                    mode=GameMode(row.mode),
                    variant=GameVariant(row.variant),
                    checkout_mode=CheckoutMode(row.checkout_mode),
                    status=effective_status(GameStatus(row.status), row.updated_at),
                    players=players,
                    winner_index=next(
                        (
                            index
                            for index, player in enumerate(players)
                            if player.remaining == 0
                        ),
                        None,
                    ),
                    dart_count=sum(
                        thrown.get((row.id, seat.player_index), 0) for seat in entries
                    ),
                    own_darts=own,
                    created_at=row.created_at,
                )
            )
        return summaries

    async def count(self, session: AsyncSession, user_id: str, criteria: GameFilter) -> int:
        """How many games `summaries` would page through."""
        return await session.scalar(
            select(func.count()).select_from(GameTable).where(*_history_clauses(user_id, criteria))
        ) or 0

    async def _elimination_remaining(
        self, session: AsyncSession, rows: Sequence[GameTable], seats: Sequence[Row[Any]]
    ) -> dict[tuple[str, int], int]:
        """Remaining points per seat of the elimination games among `rows`, replayed
        in throwing order because a reset depends on everyone's score at the time."""
        ids = [row.id for row in rows if GameVariant(row.variant) is GameVariant.ELIMINATION]
        if not ids:
            return {}

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
        for dart in dart_rows:
            darts.setdefault((dart.game_id, dart.turn_index), []).append(
                Dart(value=dart.value, multiplier=dart.multiplier)
            )

        remaining: dict[tuple[str, int], int] = {}
        for row in rows:
            if row.id not in ids:
                continue
            game = Game(
                id=row.id,
                mode=GameMode(row.mode),
                variant=GameVariant.ELIMINATION,
                players=[
                    Player(id=seat.player_index, name=seat.display_name, identity_id=seat.player_id)
                    for seat in seats
                    if seat.game_id == row.id
                ],
                turns=[
                    Turn(
                        player_id=turn.player_index,
                        darts=darts.get((turn.game_id, turn.turn_index), []),
                        busted=turn.busted,
                    )
                    for turn in turn_rows
                    if turn.game_id == row.id
                ],
            )
            for player in game.players:
                remaining[(row.id, player.id)] = game.remaining(player.id)
        return remaining

    async def is_recent(self, session: AsyncSession, game_id: str) -> bool:
        """Whether the game can still be resumed, or followed by a rematch that
        takes over its seats."""
        try:
            UUID(game_id)
        except ValueError:
            return False

        row = (
            await session.execute(
                select(GameTable.status, GameTable.updated_at).where(GameTable.id == game_id)
            )
        ).one_or_none()
        if row is None:
            return False
        return is_resumable(row.status == GameStatus.FINISHED.value, row.updated_at)

    async def rematch_seats(
        self, session: AsyncSession, game_id: str
    ) -> dict[str, PlayerIdentity]:
        """The identities seated in the game a rematch follows, keyed by id."""
        try:
            UUID(game_id)
        except ValueError:
            return {}

        rows = (
            await session.execute(
                select(PlayerTable)
                .join(GamePlayerTable, GamePlayerTable.player_id == PlayerTable.id)
                .where(GamePlayerTable.game_id == game_id)
            )
        ).scalars().all()
        return {
            row.id: PlayerIdentity(id=row.id, display_name=row.display_name, user_id=row.user_id)
            for row in rows
        }

    async def set_status(
        self, session: AsyncSession, game_id: str, user_id: str, status: GameStatus
    ) -> bool:
        """Mark a game discarded, or take that back. Scoped to the owner, so one
        account cannot rewrite another's history. Returns whether a row matched."""
        try:
            UUID(game_id)
        except ValueError:
            return False

        result = await session.execute(
            update(GameTable)
            .where(GameTable.id == game_id, GameTable.owner_user_id == user_id)
            .values(status=status.value)
        )
        return result.rowcount > 0

    async def _load(self, session: AsyncSession, game_id: str, *, lock: bool) -> Game | None:
        # Ids reach this from a url, a shared link and a socket path, so one
        # that is not a uuid at all is an ordinary miss rather than a 500.
        try:
            UUID(game_id)
        except ValueError:
            return None

        statement = select(GameTable).where(GameTable.id == game_id)
        if lock:
            statement = statement.with_for_update()

        row = (await session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None

        entries = (
            await session.execute(
                select(
                    GamePlayerTable.player_index,
                    PlayerTable.display_name,
                    GamePlayerTable.player_id,
                )
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(GamePlayerTable.game_id == game_id)
                .order_by(GamePlayerTable.player_index)
            )
        ).all()

        turn_rows = (
            await session.execute(
                select(TurnTable)
                .where(TurnTable.game_id == game_id)
                .order_by(TurnTable.turn_index)
            )
        ).scalars().all()

        dart_rows = (
            await session.execute(
                select(DartTable)
                .where(DartTable.game_id == game_id)
                .order_by(DartTable.turn_index, DartTable.dart_index)
            )
        ).scalars().all()

        darts: dict[int, list[Dart]] = {}
        for dart in dart_rows:
            position = None if dart.pos_x is None else (dart.pos_x, dart.pos_y)
            darts.setdefault(dart.turn_index, []).append(
                Dart(value=dart.value, multiplier=dart.multiplier, position=position)
            )

        preferred = await self._preferred_doubles(session, [entry[2] for entry in entries])

        return Game(
            id=row.id,
            mode=GameMode(row.mode),
            variant=GameVariant(row.variant),
            players=[
                Player(
                    id=index,
                    name=name,
                    identity_id=identity_id,
                    preferred_doubles=preferred.get(identity_id, ()),
                )
                for index, name, identity_id in entries
            ],
            checkout_mode=CheckoutMode(row.checkout_mode),
            evaluation_enabled=row.evaluation_enabled,
            current_player_index=row.current_player_index,
            turns=[
                Turn(
                    player_id=turn.player_index,
                    darts=darts.get(turn.turn_index, []),
                    busted=turn.busted,
                )
                for turn in turn_rows
            ],
            shadow_darts=[_dart_from_json(dart) for dart in row.shadow_darts],
            revision=row.revision,
            updated_at=row.updated_at,
        )


    async def _preferred_doubles(
        self, session: AsyncSession, identity_ids: list[str]
    ) -> dict[str, tuple[int, ...]]:
        """The preferred finishing doubles of each identity linked to an account."""
        rows = (
            await session.execute(
                select(PlayerTable.id, UserSettingsTable.preferred_doubles)
                .join(UserSettingsTable, UserSettingsTable.user_id == PlayerTable.user_id)
                .where(PlayerTable.id.in_(identity_ids))
            )
        ).all()
        return {row.id: tuple(row.preferred_doubles) for row in rows}


def _dart_json(dart: Dart) -> dict[str, Any]:
    return {
        "value": dart.value,
        "multiplier": dart.multiplier,
        "position": list(dart.position) if dart.position is not None else None,
    }


def _dart_from_json(data: dict[str, Any]) -> Dart:
    position = data.get("position")
    return Dart(
        value=data["value"],
        multiplier=data["multiplier"],
        position=(position[0], position[1]) if position is not None else None,
    )


def _history_clauses(user_id: str, criteria: GameFilter) -> list[ColumnElement[bool]]:
    """The account's games narrowed by `criteria`, with `abandoned` derived as `effective_status` does."""
    seated = (
        select(GamePlayerTable.game_id)
        .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
        .where(PlayerTable.user_id == user_id)
    )
    clauses: list[ColumnElement[bool]] = [
        or_(GameTable.owner_user_id == user_id, GameTable.id.in_(seated))
    ]
    if criteria.variant is not None:
        clauses.append(GameTable.variant == criteria.variant.value)
    if criteria.mode is not None:
        clauses.append(GameTable.mode == int(criteria.mode))
    if criteria.status is not None:
        cutoff = datetime.now(UTC) - ABANDON_AFTER
        active = GameTable.status == GameStatus.ACTIVE.value
        match criteria.status:
            case GameStatus.ACTIVE:
                clauses.append(and_(active, GameTable.updated_at > cutoff))
            case GameStatus.ABANDONED:
                clauses.append(and_(active, GameTable.updated_at <= cutoff))
            case _:
                clauses.append(GameTable.status == criteria.status.value)
    if criteria.opponent_id is not None:
        clauses.append(
            GameTable.id.in_(
                select(GamePlayerTable.game_id).where(
                    GamePlayerTable.player_id == criteria.opponent_id
                )
            )
        )
    if criteria.since is not None:
        clauses.append(GameTable.created_at >= criteria.since)
    if criteria.until is not None:
        clauses.append(GameTable.created_at < criteria.until)
    return clauses

repository = GameRepository()
