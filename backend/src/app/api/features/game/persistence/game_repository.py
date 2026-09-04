"""Loads and stores the game aggregate.

The server is the source of truth for every score, so a game is read fresh for
each command and written back inside the same transaction (see
docs/feature/persistenz.md §5.1/§5.2).
"""

from uuid import uuid4

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
from app.api.features.player.persistence.player import PlayerTable

# Games carry a foreign key to `users`, so that table has to be registered too.
from app.api import tables  # noqa: F401


class GameRepository:
    async def create(
        self,
        session: AsyncSession,
        mode: GameMode,
        player_names: list[str],
        checkout_mode: CheckoutMode,
        owner_user_id: str | None = None,
    ) -> Game:
        """Names are expected to be validated and non-empty (see the router).

        Every participant gets a `players` row, guests included — without one
        there would be nothing for the address book to complete later (§4.1).
        """
        game = Game(
            id=uuid4().hex,
            mode=mode,
            players=[Player(id=seat, name=name) for seat, name in enumerate(player_names)],
            checkout_mode=checkout_mode,
        )

        session.add(
            GameTable(
                id=game.id,
                mode=int(mode),
                checkout_mode=checkout_mode.value,
                status=GameStatus.ACTIVE.value,
                current_player_index=game.current_player_index,
                revision=game.revision,
                owner_user_id=owner_user_id,
            )
        )
        entries = [
            (index, uuid4().hex, name) for index, name in enumerate(player_names)
        ]
        session.add_all(
            PlayerTable(id=player_id, display_name=name) for _, player_id, name in entries
        )
        # Flush the rows `game_players` points at before adding it: no
        # relationships are declared, so the unit of work does not order the
        # inserts by foreign key on its own.
        await session.flush()

        session.add_all(
            GamePlayerTable(game_id=game.id, player_index=index, player_id=player_id)
            for index, player_id, _ in entries
        )
        await session.flush()

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
