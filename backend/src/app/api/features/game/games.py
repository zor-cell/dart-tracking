"""Session lifecycle over HTTP.

Only the two calls a device makes *around* the socket live here: creating a game
(there is no game id yet to connect to) and reading its state (initial load,
restore after a refresh, and the check that a shared link still points at a live
game — a 404 says it plainly).

Everything that *changes* a game runs over the WebSocket instead, so one
mutation reaches every device in the room on one path (core/socket/socket.py).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.services import rate_limit
from app.api.core.socket.services.game_hub import hub
from app.api.features.auth.services.current_user import AuthenticatedUser, CurrentUser
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KILLER_NUMBERS
from app.api.features.game.domain.player_count import PlayerCount
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_detail import GameDetailDto
from app.api.features.game.dto.game_page import GamePageDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_status_update import GameStatusUpdateDto
from app.api.features.game.dto.game_summary import GameSummaryDto
from app.api.features.game.dto.player_slot import PlayerSlotDto
from app.api.features.game.dto.quick_start import QuickStartDto
from app.api.features.game.dto.rematch_started import RematchStartedDto
from app.api.features.game.persistence.game_repository import repository
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.api.features.statistics.domain.player_statistics import PlayerStatistics
from app.infrastructure import database

router = APIRouter(prefix="/games", tags=["Game"])

# Games started without an account, per IP per hour.
_ANONYMOUS_GAME_LIMIT, _ANONYMOUS_GAME_WINDOW = 30, 60 * 60

# Killer needs someone to knock out, and a number of its own for everyone.
_KILLER_PLAYERS = range(2, len(KILLER_NUMBERS) + 1)


async def _resolve_players(
    session: AsyncSession,
    slots: list[PlayerSlotDto],
    owner_user_id: str | None,
    *,
    user_id: str | None,
    seated: dict[str, PlayerIdentity],
    recent: bool,
) -> list[PlayerIdentity]:
    """Turn the seats into identities: look up the chosen ones, reuse or create a
    row for every typed name. A chosen identity is the caller's, or `seated` in the
    game this is a rematch of: taken as is while that is `recent`, by name after."""
    claimed = [slot.player_id for slot in slots if slot.player_id]
    if claimed and user_id is None and not seated:
        raise HTTPException(status_code=401, detail="authentication required")
    if len(set(claimed)) != len(claimed):
        raise HTTPException(status_code=422, detail="a player can only take one seat")

    owned = await players.owned(session, claimed, user_id) if user_id else {}
    if any(id not in owned and id not in seated for id in claimed):
        raise HTTPException(status_code=422, detail="unknown player identity")

    resolved: list[PlayerIdentity] = []
    for slot in slots:
        if slot.player_id in owned or (slot.player_id in seated and recent):
            resolved.append(owned.get(slot.player_id) or seated[slot.player_id])
            continue
        name = seated[slot.player_id].display_name if slot.player_id else slot.name
        existing = (
            await players.find_by_name(session, owner_user_id, name)
            if owner_user_id
            else None
        )
        resolved.append(
            existing or await players.create(session, name, owner_user_id=owner_user_id)
        )

    if len({identity.id for identity in resolved}) != len(resolved):
        raise HTTPException(status_code=422, detail="a player can only take one seat")
    return resolved


@router.post("", response_model=GameStateDto, status_code=201)
async def create_game(body: GameConfigDto, user: CurrentUser, request: Request) -> GameStateDto:
    if not body.players:
        raise HTTPException(status_code=422, detail="at least one player is required")
    points = body.variant.counts_points
    if points and body.mode is None:
        raise HTTPException(status_code=422, detail="mode is required")
    if body.variant is GameVariant.KILLER and len(body.players) not in _KILLER_PLAYERS:
        raise HTTPException(status_code=422, detail="killer needs two to twenty players")
    if body.variant is GameVariant.ELIMINATION and len(body.players) < 2:
        raise HTTPException(status_code=422, detail="elimination needs at least two players")
    if user is None:
        await rate_limit.enforce(
            "anonymous-game",
            rate_limit.client_ip(request),
            _ANONYMOUS_GAME_LIMIT,
            _ANONYMOUS_GAME_WINDOW,
        )

    # Without an account the game has no owner, and every seat a rematch does not
    # carry over is a fresh guest.
    owner_id = user.id if user else None

    async with database.session_scope() as session:
        seated: dict[str, PlayerIdentity] = {}
        recent = False
        if body.rematch_of:
            seated = await repository.rematch_seats(session, body.rematch_of)
            recent = await repository.is_recent(session, body.rematch_of)
        identities = await _resolve_players(
            session,
            body.players,
            owner_id,
            user_id=owner_id,
            seated=seated,
            recent=recent,
        )
        game = await repository.create(
            session,
            body.mode if points else None,
            identities,
            body.variant,
            (body.checkout_mode or CheckoutMode.DOUBLE_OUT) if points else None,
            owner_user_id=owner_id,
            evaluation_enabled=body.evaluation_enabled and user is not None and user.is_admin,
            options=body.options(),
            finish=body.finish(),
        )

    if body.rematch_of:
        await hub.broadcast(body.rematch_of, RematchStartedDto(game_id=game.id))

    return GameStateDto.from_entity(game)


@router.get("", response_model=GamePageDto)
async def list_games(
    user: AuthenticatedUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=64),
    variant: list[GameVariant] = Query([]),
    mode: list[GameMode] = Query([]),
    checkout_mode: list[CheckoutMode] = Query([], alias="checkoutMode"),
    status: list[GameStatus] = Query([]),
    opponent: list[UUID] = Query([]),
    players: list[PlayerCount] = Query([]),
    since: datetime | None = None,
    until: datetime | None = None,
    min_visit: int | None = Query(None, ge=1, le=180, alias="minVisit"),
) -> GamePageDto:
    """My games — played in or written down — one page at a time."""
    criteria = GameFilter(
        query=q.strip() or None,
        variants=tuple(variant),
        modes=tuple(mode),
        checkout_modes=tuple(checkout_mode),
        statuses=tuple(status),
        opponent_ids=tuple(str(id) for id in opponent),
        player_counts=tuple(players),
        since=since,
        until=until,
        min_visit=min_visit,
    )
    async with database.session_scope() as session:
        summaries = await repository.summaries(
            session, user.id, limit=limit, offset=offset, criteria=criteria
        )
        total = await repository.count(session, user.id, criteria)

    return GamePageDto(
        items=[GameSummaryDto.from_entity(summary) for summary in summaries], total=total
    )


@router.patch("/{game_id}", status_code=204)
async def update_status(
    game_id: str, body: GameStatusUpdateDto, user: AuthenticatedUser
) -> None:
    """Take a game out of this account's list and statistics, or put it back. The
    other players keep it, whoever set it up."""
    async with database.session_scope() as session:
        changed = await repository.set_hidden(
            session, game_id, user.id, body.status == GameStatus.DISCARDED
        )

    if not changed:
        raise HTTPException(status_code=404, detail="game not found")


@router.post("/{game_id}/resume", status_code=204)
async def resume_game(game_id: str, user: AuthenticatedUser) -> None:
    """Take up a game that is still running or was left, but not won."""
    async with database.session_scope() as session:
        resumed = await repository.resume(session, game_id, user.id)

    if not resumed:
        raise HTTPException(status_code=404, detail="game not found")


@router.get("/quick-start", response_model=QuickStartDto | None)
async def get_quick_start(user: AuthenticatedUser) -> QuickStartDto | None:
    """The setup this account plays most, with the players of its latest game; null
    before the account has played."""
    async with database.session_scope() as session:
        found = await repository.quick_start(session, user.id)

    return None if found is None else QuickStartDto.from_entity(*found)


@router.get("/{game_id}", response_model=GameStateDto)
async def get_game(game_id: str) -> GameStateDto:
    async with database.session_scope() as session:
        game = await repository.get(session, game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="game not found")

    return GameStateDto.from_entity(game)


@router.get("/{game_id}/detail", response_model=GameDetailDto)
async def get_game_detail(game_id: str, user: AuthenticatedUser) -> GameDetailDto:
    """A game with its visits and per-player figures, for its players and its owner only."""
    async with database.session_scope() as session:
        record = await repository.record_for(session, game_id, user.id)
        game = await repository.get(session, game_id) if record is not None else None

    if record is None or game is None:
        raise HTTPException(status_code=404, detail="game not found")

    statistics = []
    starts = game.remaining_before_turns() if game.variant.counts_points else []
    for player in game.players if starts else []:
        entry = PlayerStatistics()
        own = [
            (turn, start)
            for turn, start in zip(game.turns, starts, strict=True)
            if turn.player_id == player.id and turn.darts
        ]
        entry.add_leg(
            game.mode,
            game.checkout_mode,
            [turn for turn, _ in own],
            starts=[start for _, start in own],
        )
        statistics.append(entry)

    return GameDetailDto.from_entity(game, record, statistics)
