"""Session lifecycle over HTTP.

Only the two calls a device makes *around* the socket live here: creating a game
(there is no game id yet to connect to) and reading its state (initial load,
restore after a refresh, and the check that a shared link still points at a live
game — a 404 says it plainly).

Everything that *changes* a game runs over the WebSocket instead, so one
mutation reaches every device in the room on one path (core/socket/socket.py).
"""

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.services import rate_limit
from app.api.core.socket.services.game_hub import hub
from app.api.features.auth.services.current_user import AuthenticatedUser, CurrentUser
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_status_update import GameStatusUpdateDto
from app.api.features.game.dto.game_summary import GameSummaryDto
from app.api.features.game.dto.player_slot import PlayerSlotDto
from app.api.features.game.dto.rematch_started import RematchStartedDto
from app.api.features.game.persistence.game_repository import repository
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.infrastructure import database

router = APIRouter(prefix="/games", tags=["Game"])

# Games started without an account, per IP per hour.
_ANONYMOUS_GAME_LIMIT, _ANONYMOUS_GAME_WINDOW = 30, 60 * 60


async def _resolve_players(
    session: AsyncSession,
    slots: list[PlayerSlotDto],
    owner_user_id: str | None,
    *,
    may_claim: bool,
) -> list[PlayerIdentity]:
    """Turn the seats into identities: look up the chosen ones, reuse or create a
    row for every typed name. The display name of a chosen identity comes from
    the database, never from the request."""
    claimed = [slot.player_id for slot in slots if slot.player_id]
    if claimed and not may_claim:
        raise HTTPException(status_code=401, detail="authentication required")
    if len(set(claimed)) != len(claimed):
        raise HTTPException(status_code=422, detail="a player can only take one seat")

    known = (
        await players.owned(session, claimed, owner_user_id) if owner_user_id else {}
    )
    if len(known) != len(claimed):
        raise HTTPException(status_code=422, detail="unknown player identity")

    resolved: list[PlayerIdentity] = []
    for slot in slots:
        if slot.player_id:
            resolved.append(known[slot.player_id])
            continue
        existing = (
            await players.find_by_name(session, owner_user_id, slot.name)
            if owner_user_id
            else None
        )
        resolved.append(
            existing
            or await players.create(session, slot.name, owner_user_id=owner_user_id)
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

    # Without an account the game has no owner and every seat is a guest, unless
    # it is a rematch: that keeps the previous game's owner and its address book.
    owner_id = user.id if user else None

    async with database.session_scope() as session:
        if owner_id is None and body.rematch_of:
            owner_id = await repository.rematch_owner(session, body.rematch_of)
        identities = await _resolve_players(
            session, body.players, owner_id, may_claim=user is not None
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


@router.get("", response_model=list[GameSummaryDto])
async def list_games(
    user: AuthenticatedUser, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[GameSummaryDto]:
    """My games — played in or written down."""
    async with database.session_scope() as session:
        summaries = await repository.summaries(session, user.id, limit=limit, offset=offset)

    return [GameSummaryDto.from_entity(summary) for summary in summaries]


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
