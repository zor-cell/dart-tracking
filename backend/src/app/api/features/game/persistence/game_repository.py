"""Loads and stores the game aggregate.

The server is the source of truth for every score, so a game is read fresh for
each command and written back inside the same transaction.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Row,
    Select,
    and_,
    case,
    delete,
    func,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_claim import ClaimOutcome
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_record import GameRecord
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import (
    ABANDON_AFTER,
    MIN_ABANDONED_DARTS,
    GameStatus,
    effective_status,
    is_resumable,
)
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.game_summary import GameSummary, GameSummaryPlayer
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.quick_start import (
    PlayedSetup,
    QuickStartSeat,
    favourite,
)
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn
from app.api.features.game.persistence.clock_settings import ClockSettingsTable
from app.api.features.game.persistence.cricket_settings import CricketSettingsTable
from app.api.features.game.persistence.dart import DartTable
from app.api.features.game.persistence.elimination_settings import EliminationSettingsTable
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_hide import GameHideTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_settings import load_setups, settings_row
from app.api.features.game.persistence.killer_settings import KillerSettingsTable
from app.api.features.game.persistence.training_settings import TrainingSettingsTable
from app.api.features.game.persistence.turn import TurnTable
from app.api.features.game.persistence.x01_settings import X01SettingsTable
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable, shown_name
from app.api.features.settings.persistence.user_settings import UserSettingsTable

# How many of the account's latest games the quick start weighs.
_QUICK_START_GAMES = 100

# Games carry a foreign key to `users`, so that table has to be registered too.
from app.api import tables  # noqa: F401


class GameRepository:
    async def create(
        self,
        session: AsyncSession,
        identities: list[PlayerIdentity],
        setup: GameSetup,
        owner_user_id: str | None = None,
        evaluation_enabled: bool = False,
        claim_token_hash: str | None = None,
    ) -> Game:
        """The identities are resolved by the router, which owns the rules about
        who may take a seat. Here they are only seated, in the order given."""
        # The id is only known after the flush below — Postgres generates it.
        game = Game(
            id="",
            mode=setup.mode,
            variant=setup.variant,
            players=[
                Player(id=seat, name=identity.display_name, identity_id=identity.id)
                for seat, identity in enumerate(identities)
            ],
            checkout_mode=setup.checkout_mode,
            options=setup.options,
            finish=setup.finish,
            evaluation_enabled=evaluation_enabled,
        )

        row = GameTable(
            variant=setup.variant.value,
            status=GameStatus.ACTIVE.value,
            current_player_index=game.current_player_index,
            revision=game.revision,
            evaluation_enabled=evaluation_enabled,
            owner_user_id=owner_user_id,
            claim_token_hash=claim_token_hash,
        )
        session.add(row)
        # Flush before adding `game_players`: no relationships are declared, so
        # the unit of work does not order the inserts by foreign key on its own.
        # It is also where the server-side id arrives.
        await session.flush()

        session.add(settings_row(row.id, game.settings))
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
        hidden = await session.scalar(
            select(GameHideTable.game_id).where(
                GameHideTable.game_id == game_id, GameHideTable.user_id == user_id
            )
        )
        return GameRecord(
            status=_status(row, hidden is not None),
            created_at=row.created_at,
            finished_at=row.finished_at,
        )

    async def resume(self, session: AsyncSession, game_id: str, user_id: str) -> bool:
        """Mark an unfinished game as just touched, so an abandoned one runs again. Scoped
        to its owner and seated accounts; returns whether a row matched."""
        try:
            UUID(game_id)
        except ValueError:
            return False

        seated = (
            select(GamePlayerTable.game_id)
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .where(GamePlayerTable.game_id == game_id, PlayerTable.user_id == user_id)
        )
        result = await session.execute(
            update(GameTable)
            .where(
                GameTable.id == game_id,
                GameTable.status == GameStatus.ACTIVE.value,
                or_(GameTable.owner_user_id == user_id, GameTable.id.in_(seated)),
            )
            .values(updated_at=func.now())
        )
        return result.rowcount > 0

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
        finished = game.over
        derived = (GameStatus.FINISHED if finished else GameStatus.ACTIVE).value
        game.updated_at = await session.scalar(
            update(GameTable)
            .where(GameTable.id == game.id)
            .values(
                current_player_index=game.current_player_index,
                revision=game.revision,
                evaluation_enabled=game.evaluation_enabled,
                tracking_paused=game.tracking_paused,
                win_confirmed=game.win_confirmed,
                shadow_darts=[_dart_json(dart) for dart in game.shadow_darts],
                status=derived,
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
                ended_at=turn.ended_at,
            )
            for turn_index, turn in enumerate(game.turns)
        )
        # Turns before darts, for the reason given in `create`.
        await session.flush()

        targets = game.targets()
        session.add_all(
            DartTable(
                game_id=game.id,
                turn_index=turn_index,
                dart_index=dart_index,
                value=dart.value,
                multiplier=dart.multiplier,
                pos_x=dart.position[0] if dart.position else None,
                pos_y=dart.position[1] if dart.position else None,
                thrown_at=dart.thrown_at,
                target_value=target.value if target else None,
                target_multiplier=target.multiplier if target else None,
            )
            for turn_index, turn in enumerate(game.turns)
            for dart_index, (dart, target) in enumerate(
                zip(turn.darts, targets[turn_index], strict=True)
            )
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
        return await self._summarize(session, rows, user_id)

    async def claimable(
        self, session: AsyncSession, token_hashes: dict[str, str], user_id: str
    ) -> list[GameSummary]:
        """The ownerless games among `token_hashes` (game id to hash) whose hash matches,
        newest first."""
        ids = [game_id for game_id in token_hashes if _is_uuid(game_id)]
        if not ids:
            return []
        rows = (
            await session.execute(
                select(GameTable)
                .where(GameTable.id.in_(ids), GameTable.owner_user_id.is_(None))
                .order_by(GameTable.created_at.desc())
            )
        ).scalars().all()
        matching = [row for row in rows if row.claim_token_hash == token_hashes[row.id]]
        return await self._summarize(session, matching, user_id)

    async def claim(
        self,
        session: AsyncSession,
        game_id: str,
        token_hash: str,
        user_id: str,
        seat: int | None,
    ) -> ClaimOutcome:
        """Hand an anonymous game to the account: `seat` becomes its own entry, the other
        guests entries of its address book, reused by name where it has them."""
        if not _is_uuid(game_id):
            return ClaimOutcome.NOT_FOUND
        row = (
            await session.execute(
                select(GameTable).where(GameTable.id == game_id).with_for_update()
            )
        ).scalar_one_or_none()
        if (
            row is None
            or row.owner_user_id is not None
            or row.claim_token_hash is None
            or row.claim_token_hash != token_hash
        ):
            return ClaimOutcome.NOT_FOUND

        seats = (
            await session.execute(
                select(GamePlayerTable.player_index, PlayerTable)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(GamePlayerTable.game_id == game_id)
                .order_by(GamePlayerTable.player_index)
            )
        ).all()
        own = (
            await session.execute(
                select(PlayerTable).where(
                    PlayerTable.owner_user_id == user_id, PlayerTable.user_id == user_id
                )
            )
        ).scalar_one()
        own_seat = next((index for index, entry in seats if entry.id == own.id), None)
        if seat is not None and not 0 <= seat < len(seats):
            return ClaimOutcome.BAD_SEAT
        if own_seat is not None and seat not in (None, own_seat):
            return ClaimOutcome.BAD_SEAT
        if seat is not None and seat != own_seat and seats[seat][1].user_id is not None:
            return ClaimOutcome.BAD_SEAT

        taken = {entry.id for _, entry in seats if _keeps_seat(entry, user_id)}
        if own_seat is None and seat is not None:
            taken.add(own.id)
        for index, entry in seats:
            if index == seat:
                chosen = own.id
            elif _keeps_seat(entry, user_id):
                continue
            else:
                chosen = await self._guest_entry(session, entry, user_id, taken)
                taken.add(chosen)
            if chosen != entry.id:
                await session.execute(
                    update(GamePlayerTable)
                    .where(
                        GamePlayerTable.game_id == game_id,
                        GamePlayerTable.player_index == index,
                    )
                    .values(player_id=chosen)
                )

        row.owner_user_id = user_id
        row.claim_token_hash = None
        await session.flush()
        return ClaimOutcome.CLAIMED

    async def _guest_entry(
        self, session: AsyncSession, guest: PlayerTable, user_id: str, taken: set[str]
    ) -> str:
        """The address book entry a claimed game's guest sits as: one of the same name,
        else the guest itself when nobody owns it, else a new one."""
        if guest.display_name is not None:
            same_name = (
                await session.execute(
                    select(PlayerTable.id)
                    .where(
                        PlayerTable.owner_user_id == user_id,
                        PlayerTable.user_id.is_distinct_from(user_id),
                        func.lower(PlayerTable.display_name) == guest.display_name.lower(),
                        PlayerTable.id.not_in(taken) if taken else true(),
                    )
                    .order_by(PlayerTable.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if same_name is not None:
                return same_name
        if guest.owner_user_id is None:
            guest.owner_user_id = user_id
            return guest.id
        entry = PlayerTable(display_name=guest.display_name, owner_user_id=user_id)
        session.add(entry)
        await session.flush()
        return entry.id

    async def _summarize(
        self, session: AsyncSession, rows: Sequence[GameTable], user_id: str
    ) -> list[GameSummary]:
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

        hidden = set(
            (
                await session.execute(
                    select(GameHideTable.game_id).where(
                        GameHideTable.user_id == user_id, GameHideTable.game_id.in_(ids)
                    )
                )
            ).scalars()
        )

        scored = {(t.game_id, t.player_index): t.scored for t in tallies}
        thrown = {(t.game_id, t.player_index): t.darts for t in tallies}
        setups = await load_setups(session, {row.id: GameVariant(row.variant) for row in rows})
        replayed = await self._replayed(session, setups, seats)

        seats_of = by_game(seats)
        summaries: list[GameSummary] = []
        for row in rows:
            entries = seats_of.get(row.id, [])
            game = replayed.get(row.id)
            players = [
                GameSummaryPlayer(
                    name=shown_name(seat.display_name),
                    remaining=_summary_remaining(
                        row.id, setups[row.id].mode, seat.player_index, game, scored
                    ),
                    is_me=seat.user_id == user_id,
                )
                for seat in entries
            ]
            if game is not None:
                winner = game.winner
                winner_index = None if winner is None else winner.id
            else:
                winner_index = next(
                    (index for index, player in enumerate(players) if player.remaining == 0),
                    None,
                )
            summaries.append(
                GameSummary(
                    id=row.id,
                    setup=setups[row.id],
                    status=_status(row, row.id in hidden),
                    players=players,
                    winner_index=winner_index,
                    dart_count=sum(
                        thrown.get((row.id, seat.player_index), 0) for seat in entries
                    ),
                    created_at=row.created_at,
                )
            )
        return summaries

    async def count(self, session: AsyncSession, user_id: str, criteria: GameFilter) -> int:
        """How many games `summaries` would page through."""
        return await session.scalar(
            select(func.count()).select_from(GameTable).where(*_history_clauses(user_id, criteria))
        ) or 0

    async def _replayed(
        self, session: AsyncSession, setups: dict[str, GameSetup], seats: Sequence[Row[Any]]
    ) -> dict[str, Game]:
        """The games among `setups` whose standing cannot be summed in SQL, replayed in
        throwing order: an elimination reset or a variant's rules depend on everyone."""
        ids = [id for id, setup in setups.items() if setup.variant is not GameVariant.X01]
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

        seats_of, turns_of = by_game(seats), by_game(turn_rows)
        games: dict[str, Game] = {}
        for game_id in ids:
            setup = setups[game_id]
            games[game_id] = Game(
                id=game_id,
                mode=setup.mode,
                variant=setup.variant,
                options=setup.options,
                players=[
                    Player(
                        id=seat.player_index,
                        name=shown_name(seat.display_name),
                        identity_id=seat.player_id,
                    )
                    for seat in seats_of.get(game_id, [])
                ],
                turns=[
                    Turn(
                        player_id=turn.player_index,
                        darts=darts.get((turn.game_id, turn.turn_index), []),
                        busted=turn.busted,
                    )
                    for turn in turns_of.get(game_id, [])
                ],
            )
        return games

    async def quick_start(
        self, session: AsyncSession, user_id: str
    ) -> tuple[PlayedSetup, list[QuickStartSeat]] | None:
        """The setup this account plays most among its recent games with darts, and
        the seats of the latest game with it; None before any such game."""
        darts = select(DartTable.game_id).where(DartTable.game_id == GameTable.id).exists()
        rows = (
            await session.execute(
                select(GameTable)
                .where(_involving(user_id), GameTable.id.not_in(hidden_by(user_id)), darts)
                .order_by(GameTable.created_at.desc())
                .limit(_QUICK_START_GAMES)
            )
        ).scalars().all()
        setups = await load_setups(session, {row.id: GameVariant(row.variant) for row in rows})
        played = []
        for row in rows:
            stored = setups[row.id]
            setup = GameSetup.of(
                stored.variant, stored.mode, stored.checkout_mode, stored.options, stored.finish
            )
            played.append(PlayedSetup(row.id, row.created_at, setup))
        chosen = favourite(played, datetime.now(UTC))
        if chosen is None:
            return None

        own = await session.scalar(
            select(PlayerTable.id).where(
                PlayerTable.owner_user_id == user_id, PlayerTable.user_id == user_id
            )
        )
        entries = (
            await session.execute(
                select(PlayerTable)
                .join(GamePlayerTable, GamePlayerTable.player_id == PlayerTable.id)
                .where(GamePlayerTable.game_id == chosen.game_id)
                .order_by(GamePlayerTable.player_index)
            )
        ).scalars().all()
        seats = []
        for entry in entries:
            name = shown_name(entry.display_name)
            if entry.user_id == user_id and own is not None:
                seats.append(QuickStartSeat(own, name))
            elif entry.owner_user_id == user_id:
                seats.append(QuickStartSeat(entry.id, name))
            else:
                seats.append(QuickStartSeat(None, name))
        return chosen, seats

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
            row.id: PlayerIdentity(
                id=row.id, display_name=shown_name(row.display_name), user_id=row.user_id
            )
            for row in rows
        }

    async def set_hidden(
        self, session: AsyncSession, game_id: str, user_id: str, hidden: bool
    ) -> bool:
        """Hide a game from this account's own list and statistics, or show it again.
        Only its owner and seated accounts may; returns whether the game was theirs."""
        if await self.record_for(session, game_id, user_id) is None:
            return False

        if hidden:
            await session.execute(
                insert(GameHideTable)
                .values(user_id=user_id, game_id=game_id)
                .on_conflict_do_nothing()
            )
        else:
            await session.execute(
                delete(GameHideTable).where(
                    GameHideTable.user_id == user_id, GameHideTable.game_id == game_id
                )
            )
        return True

    async def forget_account(self, session: AsyncSession, user_id: str) -> None:
        """For a deleted account: drop its games that no other account is part of,
        and leave the shared ones to the others without an owner."""
        others_seated = (
            select(GamePlayerTable.game_id)
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .where(PlayerTable.user_id.is_not(None), PlayerTable.user_id != user_id)
        )
        owned_by_others = and_(
            GameTable.owner_user_id.is_not(None), GameTable.owner_user_id != user_id
        )
        await session.execute(
            delete(GameTable).where(
                _involving(user_id),
                ~owned_by_others,
                GameTable.id.not_in(others_seated),
            )
        )
        await session.execute(
            update(GameTable).where(GameTable.owner_user_id == user_id).values(owner_user_id=None)
        )

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

        preferred = await self._preferred_doubles(session, [entry[2] for entry in entries])
        setup = (await load_setups(session, {row.id: GameVariant(row.variant)}))[row.id]
        return _assemble(row, setup, entries, turn_rows, dart_rows, preferred)

    async def many(self, session: AsyncSession, game_ids: Sequence[str]) -> dict[str, Game]:
        """The games `game_ids` names, each replayable, loaded in a few queries."""
        if not game_ids:
            return {}
        rows = (
            await session.execute(select(GameTable).where(GameTable.id.in_(game_ids)))
        ).scalars().all()
        seats = (
            await session.execute(
                select(
                    GamePlayerTable.game_id,
                    GamePlayerTable.player_index,
                    PlayerTable.display_name,
                    GamePlayerTable.player_id,
                )
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(GamePlayerTable.game_id.in_(game_ids))
                .order_by(GamePlayerTable.game_id, GamePlayerTable.player_index)
            )
        ).all()
        turns = (
            await session.execute(
                select(TurnTable)
                .where(TurnTable.game_id.in_(game_ids))
                .order_by(TurnTable.game_id, TurnTable.turn_index)
            )
        ).scalars().all()
        darts = (
            await session.execute(
                select(DartTable)
                .where(DartTable.game_id.in_(game_ids))
                .order_by(DartTable.game_id, DartTable.turn_index, DartTable.dart_index)
            )
        ).scalars().all()
        setups = await load_setups(session, {row.id: GameVariant(row.variant) for row in rows})
        seats_of, turns_of, darts_of = by_game(seats), by_game(turns), by_game(darts)
        return {
            row.id: _assemble(
                row,
                setups[row.id],
                [(seat[1], seat[2], seat[3]) for seat in seats_of.get(row.id, [])],
                turns_of.get(row.id, []),
                darts_of.get(row.id, []),
                {},
            )
            for row in rows
        }


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


class _OfGame(Protocol):
    game_id: str


def by_game[R: _OfGame](rows: Sequence[R]) -> dict[str, list[R]]:
    """`rows` split by their `game_id`, each game's in the order they came."""
    grouped: dict[str, list[R]] = {}
    for row in rows:
        grouped.setdefault(row.game_id, []).append(row)
    return grouped


def _assemble(
    row: GameTable,
    setup: GameSetup,
    entries: Sequence[tuple[int, str | None, str]],
    turn_rows: Sequence[TurnTable],
    dart_rows: Sequence[DartTable],
    preferred: dict[str, tuple[int, ...]],
) -> Game:
    """A game from its rows: seats as (index, name, player id), turns and darts in order."""
    darts: dict[int, list[Dart]] = {}
    for dart in dart_rows:
        position = None if dart.pos_x is None else (dart.pos_x, dart.pos_y)
        darts.setdefault(dart.turn_index, []).append(
            Dart(
                value=dart.value,
                multiplier=dart.multiplier,
                position=position,
                thrown_at=dart.thrown_at,
            )
        )
    variant = setup.variant
    return Game(
        id=row.id,
        mode=setup.mode,
        variant=variant,
        options=setup.options,
        finish=setup.finish,
        players=[
            Player(
                id=index,
                name=shown_name(name),
                identity_id=identity_id,
                preferred_doubles=preferred.get(identity_id, ()),
            )
            for index, name, identity_id in entries
        ],
        checkout_mode=setup.checkout_mode,
        evaluation_enabled=row.evaluation_enabled,
        tracking_paused=row.tracking_paused,
        win_confirmed=row.win_confirmed,
        ended=variant.open_ended and row.status == GameStatus.FINISHED.value,
        current_player_index=row.current_player_index,
        turns=[
            Turn(
                player_id=turn.player_index,
                darts=darts.get(turn.turn_index, []),
                busted=turn.busted,
                ended_at=turn.ended_at,
            )
            for turn in turn_rows
        ],
        shadow_darts=[_dart_from_json(dart) for dart in row.shadow_darts],
        revision=row.revision,
        updated_at=row.updated_at,
    )


def _summary_remaining(
    game_id: str,
    mode: GameMode | None,
    seat: int,
    game: Game | None,
    scored: dict[tuple[str, int], int],
) -> int | None:
    """Points a seat still needed: summed in SQL for x01, replayed for elimination,
    none outside the points variants."""
    if mode is None:
        return None
    if game is not None:
        return game.remaining(seat)
    return mode - scored.get((game_id, seat), 0)


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
    """The account's games narrowed by `criteria`, with the status derived as `_status` does."""
    clauses: list[ColumnElement[bool]] = [_involving(user_id)]
    cutoff = datetime.now(UTC) - ABANDON_AFTER
    hidden = GameTable.id.in_(hidden_by(user_id))
    if criteria.statuses:
        clauses.append(
            or_(*(_status_clause(status, cutoff, hidden) for status in criteria.statuses))
        )
    else:
        darts = (
            select(func.count())
            .select_from(DartTable)
            .where(DartTable.game_id == GameTable.id)
            .correlate(GameTable)
            .scalar_subquery()
        )
        short_abandoned = and_(
            _status_clause(GameStatus.ABANDONED, cutoff, hidden), darts < MIN_ABANDONED_DARTS
        )
        clauses.append(~hidden)
        clauses.append(~short_abandoned)
    if criteria.min_visit is not None:
        own_visits = (
            select(TurnTable.game_id)
            .join(
                GamePlayerTable,
                (GamePlayerTable.game_id == TurnTable.game_id)
                & (GamePlayerTable.player_index == TurnTable.player_index),
            )
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .join(
                DartTable,
                (DartTable.game_id == TurnTable.game_id)
                & (DartTable.turn_index == TurnTable.turn_index),
            )
            .where(PlayerTable.user_id == user_id, TurnTable.busted.is_(False))
            .group_by(TurnTable.game_id, TurnTable.turn_index)
            .having(func.sum(DartTable.value * DartTable.multiplier) >= criteria.min_visit)
        )
        clauses.append(GameTable.id.in_(own_visits))
    return clauses + game_filter_clauses(criteria)


def _involving(user_id: str) -> ColumnElement[bool]:
    """The games this account set up or holds a seat in."""
    seated = (
        select(GamePlayerTable.game_id)
        .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
        .where(PlayerTable.user_id == user_id)
    )
    return or_(GameTable.owner_user_id == user_id, GameTable.id.in_(seated))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _keeps_seat(entry: PlayerTable, user_id: str) -> bool:
    """Whether a claimed game's seat stays as it is: an account's player, or already
    an entry of the claiming account's address book."""
    return entry.user_id is not None or entry.owner_user_id == user_id


def _status_clause(
    status: GameStatus, cutoff: datetime, hidden: ColumnElement[bool]
) -> ColumnElement[bool]:
    """The games whose derived status is `status`, as `_status` reads it."""
    active = GameTable.status == GameStatus.ACTIVE.value
    match status:
        case GameStatus.DISCARDED:
            return hidden
        case GameStatus.ACTIVE:
            return and_(~hidden, active, GameTable.updated_at > cutoff)
        case GameStatus.ABANDONED:
            return and_(~hidden, active, GameTable.updated_at <= cutoff)
        case _:
            return and_(~hidden, GameTable.status == status.value)


def _status(row: GameTable, hidden: bool) -> GameStatus:
    """The status the reading account sees: its own hide first, then `effective_status`."""
    if hidden:
        return GameStatus.DISCARDED
    return effective_status(GameStatus(row.status), row.updated_at)


def hidden_by(user_id: str) -> Select[tuple[str]]:
    """The ids of the games this account hid."""
    return select(GameHideTable.game_id).where(GameHideTable.user_id == user_id)


def game_filter_clauses(criteria: GameFilter) -> list[ColumnElement[bool]]:
    """`criteria` as conditions on the games table, all but `statuses`, which each
    reader of the history counts its own way."""
    clauses: list[ColumnElement[bool]] = []
    if criteria.query:
        clauses.append(
            GameTable.id.in_(
                select(GamePlayerTable.game_id)
                .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
                .where(PlayerTable.display_name.icontains(criteria.query, autoescape=True))
            )
        )
    if criteria.variants:
        clauses.append(GameTable.variant.in_([variant.value for variant in criteria.variants]))
    if criteria.modes:
        scores = [int(mode) for mode in criteria.modes]
        clauses.append(_points_games(lambda table: table.start_score.in_(scores)))
    if criteria.checkout_modes:
        checkouts = [mode.value for mode in criteria.checkout_modes]
        clauses.append(_points_games(lambda table: table.checkout_mode.in_(checkouts)))
    for column, values in (
        (EliminationSettingsTable.kill, criteria.elimination_kills),
        (CricketSettingsTable.scoring, criteria.cricket_scorings),
        (KillerSettingsTable.zone, criteria.killer_zones),
        (ClockSettingsTable.zone, criteria.clock_zones),
        (TrainingSettingsTable.goal, criteria.training_goals),
        (TrainingSettingsTable.ring, criteria.training_rings),
    ):
        if values:
            chosen = [value.value for value in values]
            clauses.append(
                GameTable.id.in_(select(column.class_.game_id).where(column.in_(chosen)))
            )
    if criteria.opponent_ids:
        clauses.append(
            GameTable.id.in_(
                select(GamePlayerTable.game_id).where(
                    GamePlayerTable.player_id.in_(criteria.opponent_ids)
                )
            )
        )
    if criteria.player_counts:
        seats = (
            select(func.count())
            .select_from(GamePlayerTable)
            .where(GamePlayerTable.game_id == GameTable.id)
            .correlate(GameTable)
            .scalar_subquery()
        )
        ranges = []
        for count in criteria.player_counts:
            fewest, most = count.bounds
            ranges.append(seats >= fewest if most is None else seats.between(fewest, most))
        clauses.append(or_(*ranges))
    if criteria.since is not None:
        clauses.append(GameTable.created_at >= criteria.since)
    if criteria.until is not None:
        clauses.append(GameTable.created_at < criteria.until)
    return clauses


type _PointsTable = type[X01SettingsTable] | type[EliminationSettingsTable]


def _points_games(condition: Callable[[_PointsTable], ColumnElement[bool]]) -> ColumnElement[bool]:
    """The games of a points variant whose settings meet `condition`."""
    tables: tuple[_PointsTable, ...] = (X01SettingsTable, EliminationSettingsTable)
    return or_(
        *(GameTable.id.in_(select(table.game_id).where(condition(table))) for table in tables)
    )


repository = GameRepository()
