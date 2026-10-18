"""Loads and stores the game aggregate.

The server is the source of truth for every score, so a game is read fresh for
each command and written back inside the same transaction.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus, effective_status
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
        return game

    async def get(self, session: AsyncSession, game_id: str) -> Game | None:
        """Read without locking — for the endpoints that only display a game."""
        return await self._load(session, game_id, lock=False)

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
        self, session: AsyncSession, user_id: str, *, limit: int, offset: int
    ) -> list[GameSummary]:
        """The games this account took part in or wrote down, newest first.

        Both branches are needed: a game set up by a fellow player belongs in my
        history too, and one I only kept score for has no seat for me at all.
        """
        mine = (
            select(GamePlayerTable.game_id)
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .where(PlayerTable.user_id == user_id)
        )
        rows = (
            await session.execute(
                select(GameTable)
                .where(
                    or_(
                        GameTable.owner_user_id == user_id,
                        GameTable.id.in_(mine),
                    )
                )
                .order_by(GameTable.updated_at.desc())
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

        summaries: list[GameSummary] = []
        for row in rows:
            entries = [seat for seat in seats if seat.game_id == row.id]
            players = [
                GameSummaryPlayer(
                    name=seat.display_name,
                    remaining=row.mode - scored.get((row.id, seat.player_index), 0),
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

        return Game(
            id=row.id,
            mode=GameMode(row.mode),
            variant=GameVariant(row.variant),
            players=[
                Player(id=index, name=name, identity_id=identity_id)
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


repository = GameRepository()
