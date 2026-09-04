"""Loads and stores the game aggregate.

The server is the source of truth for every score, so a game is read fresh for
each command and written back inside the same transaction (see
docs/feature/persistenz.md §5.1/§5.2).
"""

from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
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
        checkout_mode: CheckoutMode,
        owner_user_id: str | None = None,
    ) -> Game:
        """The identities are resolved by the router, which owns the rules about
        who may take a seat. Here they are only seated, in the order given."""
        # The id is only known after the flush below — Postgres generates it.
        game = Game(
            id="",
            mode=mode,
            players=[
                Player(id=seat, name=identity.display_name)
                for seat, identity in enumerate(identities)
            ],
            checkout_mode=checkout_mode,
        )

        row = GameTable(
            mode=int(mode),
            checkout_mode=checkout_mode.value,
            status=GameStatus.ACTIVE.value,
            current_player_index=game.current_player_index,
            revision=game.revision,
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
        await session.execute(
            update(GameTable)
            .where(GameTable.id == game.id)
            .values(
                current_player_index=game.current_player_index,
                revision=game.revision,
                status=(GameStatus.FINISHED if finished else GameStatus.ACTIVE).value,
                finished_at=func.now() if finished else None,
            )
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
                select(GamePlayerTable.player_index, PlayerTable.display_name)
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
            players=[Player(id=index, name=name) for index, name in entries],
            checkout_mode=CheckoutMode(row.checkout_mode),
            current_player_index=row.current_player_index,
            turns=[
                Turn(
                    player_id=turn.player_index,
                    darts=darts.get(turn.turn_index, []),
                    busted=turn.busted,
                )
                for turn in turn_rows
            ],
            revision=row.revision,
        )


repository = GameRepository()
