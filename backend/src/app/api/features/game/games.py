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
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_detail import GameDetailDto
from app.api.features.game.dto.game_page import GamePageDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_status_update import GameStatusUpdateDto
from app.api.features.game.dto.game_summary import GameSummaryDto
from app.api.features.game.dto.player_slot import PlayerSlotDto
from app.api.features.game.dto.rematch_started import RematchStartedDto
from app.api.features.game.persistence.game_repository import repository
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.api.features.statistics.domain.player_statistics import PlayerStatistics
from app.infrastructure import database

router = APIRouter(prefix="/games", tags=["Game"])

# Games started without an account, per IP per hour.
_ANONYMOUS_GAME_LIMIT, _ANONYMOUS_GAME_WINDOW = 30, 60 * 60


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
            body.mode,
            identities,
            body.variant,
            body.checkout_mode,
            owner_user_id=owner_id,
            evaluation_enabled=body.evaluation_enabled and user is not None and user.is_admin,
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
    variant: GameVariant | None = None,
    mode: GameMode | None = None,
    status: GameStatus | None = None,
    opponent: UUID | None = None,
    min_players: int | None = Query(None, ge=1, alias="minPlayers"),
    max_players: int | None = Query(None, ge=1, alias="maxPlayers"),
    since: datetime | None = None,
    until: datetime | None = None,
    min_visit: int | None = Query(None, ge=1, le=180, alias="minVisit"),
) -> GamePageDto:
    """My games — played in or written down — one page at a time."""
    criteria = GameFilter(
        query=q.strip() or None,
        variant=variant,
        mode=mode,
        status=status,
        opponent_id=str(opponent) if opponent else None,
        min_players=min_players,
        max_players=max_players,
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
    """Take a game out of the statistics, or put it back. The counterpart to the
    opt-out in §4.5: writing every game down and sorting out the exceptions."""
    async with database.session_scope() as session:
        # Putting a game back means restoring the status it would have had, not
        # writing `active` over a leg that was won — that would hide it from the
        # statistics just as thoroughly as the discard did.
        target = GameStatus.DISCARDED
        if body.status != GameStatus.DISCARDED:
            game = await repository.get(session, game_id)
            target = (
                GameStatus.FINISHED
                if game is not None and game.winner is not None
                else GameStatus.ACTIVE
            )

        changed = await repository.set_status(session, game_id, user.id, target)

    if not changed:
        raise HTTPException(status_code=404, detail="game not found")


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
    for player in game.players:
        entry = PlayerStatistics()
        turns = [turn for turn in game.turns if turn.player_id == player.id and turn.darts]
        entry.add_leg(game.mode, game.checkout_mode, turns)
        statistics.append(entry)

    return GameDetailDto.from_entity(game, record, statistics)
