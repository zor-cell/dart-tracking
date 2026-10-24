"""Copy one account's games from another database, such as a restored prod dump, into
an existing account of the configured database: fresh ids, co-players become guests.
See `--help` for the arguments."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Import app.* from src/, as `--app-dir src` does at runtime.
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND / "src"))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.api import tables  # noqa: E402, F401
from app.api.features.auth.persistence.user import UserTable  # noqa: E402
from app.api.features.game.persistence.dart import DartTable  # noqa: E402
from app.api.features.game.persistence.game import GameTable  # noqa: E402
from app.api.features.game.persistence.game_player import GamePlayerTable  # noqa: E402
from app.api.features.game.persistence.turn import TurnTable  # noqa: E402
from app.api.features.player.persistence.player import PlayerTable  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402


def _copy[Row](row: Row, *, fresh_id: bool = False, **changes: Any) -> Row:
    """A new, unsaved row with the same column values, some of them replaced; with
    `fresh_id` the database assigns a new id."""
    values = {column.key: getattr(row, column.key) for column in row.__mapper__.column_attrs}
    if fresh_id:
        del values["id"]
    values.update(changes)
    return type(row)(**values)


async def _revision(session: AsyncSession) -> str | None:
    return await session.scalar(text("SELECT version_num FROM alembic_version"))


async def _user(session: AsyncSession, username: str) -> UserTable | None:
    return await session.scalar(
        select(UserTable).where(func.lower(UserTable.username) == username.lower())
    )


class _AddressBook:
    """The target account's own entry and its guests, reused by name like the app does."""

    def __init__(self, session: AsyncSession, user: UserTable, anonymize: bool) -> None:
        self._session = session
        self._user = user
        self._anonymize = anonymize
        self._guests: dict[str, PlayerTable] = {}
        self._aliases: dict[str, str] = {}
        self.created = 0

    async def own(self) -> PlayerTable:
        entry = await self._session.scalar(
            select(PlayerTable).where(
                PlayerTable.owner_user_id == self._user.id,
                PlayerTable.user_id == self._user.id,
            )
        )
        if entry is None:
            entry = await self._add(self._user.display_name, user_id=self._user.id)
        return entry

    async def guest(self, name: str, *, seated: set[str]) -> PlayerTable:
        """The guest of this name, or a separate one if that one already sits in the game."""
        key = name.lower()
        if self._anonymize:
            name = self._aliases.setdefault(key, f"Gast {len(self._aliases) + 1}")
            key = name.lower()
        if key not in self._guests:
            existing = await self._session.scalar(
                select(PlayerTable)
                .where(
                    PlayerTable.owner_user_id == self._user.id,
                    func.lower(PlayerTable.display_name) == key,
                    PlayerTable.user_id.is_distinct_from(self._user.id),
                )
                .order_by(PlayerTable.created_at)
                .limit(1)
            )
            self._guests[key] = existing or await self._add(name)
        entry = self._guests[key]
        return entry if entry.id not in seated else await self._add(name)

    async def _add(self, name: str, *, user_id: str | None = None) -> PlayerTable:
        entry = PlayerTable(display_name=name, owner_user_id=self._user.id, user_id=user_id)
        self._session.add(entry)
        await self._session.flush()
        self.created += 1
        return entry


async def import_account(
    source_db: str, source_username: str, target_username: str, anonymize: bool, force: bool
) -> None:
    settings = get_settings()
    source_url = settings.model_copy(update={"postgres_db": source_db}).database_url
    source_engine = create_async_engine(source_url)
    target_engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(source_engine) as source, AsyncSession(target_engine) as target:
            source_revision, target_revision = await _revision(source), await _revision(target)
            if source_revision != target_revision:
                sys.exit(
                    f"Schema differs: {source_db} is at {source_revision}, "
                    f"{settings.postgres_db} at {target_revision}. Migrate the copy first."
                )

            source_user = await _user(source, source_username)
            if source_user is None:
                sys.exit(f"No user '{source_username}' in {source_db}.")
            target_user = await _user(target, target_username)
            if target_user is None:
                sys.exit(
                    f"No user '{target_username}' in {settings.postgres_db}; register it first."
                )

            already = await target.scalar(
                select(func.count())
                .select_from(GamePlayerTable)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(PlayerTable.user_id == target_user.id)
            )
            if already and not force:
                sys.exit(
                    f"'{target_username}' already played {already} games; "
                    "pass --force to import on top of them."
                )

            game_ids = (
                await source.scalars(
                    select(GamePlayerTable.game_id)
                    .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                    .where(PlayerTable.user_id == source_user.id)
                    .distinct()
                )
            ).all()
            games = (
                await source.scalars(
                    select(GameTable)
                    .where(GameTable.id.in_(game_ids))
                    .order_by(GameTable.created_at)
                )
            ).all()
            seats = (
                await source.scalars(
                    select(GamePlayerTable)
                    .where(GamePlayerTable.game_id.in_(game_ids))
                    .order_by(GamePlayerTable.game_id, GamePlayerTable.player_index)
                )
            ).all()
            players = {
                player.id: player
                for player in await source.scalars(
                    select(PlayerTable).where(
                        PlayerTable.id.in_({seat.player_id for seat in seats})
                    )
                )
            }
            turns = (
                await source.scalars(select(TurnTable).where(TurnTable.game_id.in_(game_ids)))
            ).all()
            darts = (
                await source.scalars(select(DartTable).where(DartTable.game_id.in_(game_ids)))
            ).all()

            copies = {
                game.id: _copy(
                    game,
                    fresh_id=True,
                    owner_user_id=target_user.id if game.owner_user_id == source_user.id else None,
                )
                for game in games
            }
            target.add_all(copies.values())
            await target.flush()
            new_ids = {old: copy.id for old, copy in copies.items()}

            book = _AddressBook(target, target_user, anonymize)
            own = await book.own()
            seated: dict[str, set[str]] = {}
            for seat in seats:
                taken = seated.setdefault(seat.game_id, set())
                player = players[seat.player_id]
                entry = (
                    own
                    if player.user_id == source_user.id
                    else await book.guest(player.display_name, seated=taken)
                )
                taken.add(entry.id)
                target.add(_copy(seat, game_id=new_ids[seat.game_id], player_id=entry.id))

            target.add_all(_copy(turn, game_id=new_ids[turn.game_id]) for turn in turns)
            await target.flush()
            target.add_all(_copy(dart, game_id=new_ids[dart.game_id]) for dart in darts)
            await target.commit()

        located = sum(dart.pos_x is not None for dart in darts)
        print(
            f"Imported {len(games)} games, {len(turns)} visits and {len(darts)} darts "
            f"({located} located) into '{target_username}'; "
            f"{book.created} address-book entries created."
        )
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True, help="database holding the restored dump")
    parser.add_argument("--from", dest="source_username", required=True, help="username there")
    parser.add_argument("--to", dest="target_username", required=True, help="username here")
    parser.add_argument("--anonymize", action="store_true", help="rename co-players to Gast 1, ...")
    parser.add_argument("--force", action="store_true", help="import into an account with games")
    args = parser.parse_args()
    asyncio.run(
        import_account(
            args.source_db, args.source_username, args.target_username, args.anonymize, args.force
        )
    )


if __name__ == "__main__":
    main()
