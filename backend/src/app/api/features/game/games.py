"""Session lifecycle over HTTP.

Only the two calls a device makes *around* the socket live here: creating a game
(there is no game id yet to connect to) and reading its state (initial load,
restore after a refresh, and the check that a shared link still points at a live
game — a 404 says it plainly).

Everything that *changes* a game runs over the WebSocket instead, so one
mutation reaches every device in the room on one path (core/socket/socket.py,
docs/feature/multi-device.md §3).
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.auth.services.current_user import CurrentUser
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.player_slot import PlayerSlotDto
from app.api.features.game.persistence.game_repository import repository
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player_repository import repository as players
from app.infrastructure import database

router = APIRouter(prefix="/games", tags=["Game"])


async def _resolve_players(
    session: AsyncSession, slots: list[PlayerSlotDto], owner_user_id: str | None
) -> list[PlayerIdentity]:
    """Turn the seats into identities: look up the chosen ones, create a row for
    every typed name. The display name of a chosen identity comes from the
    database, never from the request."""
    claimed = [slot.player_id for slot in slots if slot.player_id]
    if claimed and owner_user_id is None:
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
        else:
            resolved.append(
                await players.create(session, slot.name, owner_user_id=owner_user_id)
            )
    return resolved


@router.post("", response_model=GameStateDto, status_code=201)
async def create_game(body: GameConfigDto, user: CurrentUser) -> GameStateDto:
    if not body.players:
        raise HTTPException(status_code=422, detail="at least one player is required")

    # Anonymous play stays possible: without an account the game simply has no
    # owner, and every seat is a fresh guest (docs/feature/persistenz.md §4.4).
    owner_id = user.id if user else None

    async with database.session_scope() as session:
        identities = await _resolve_players(session, body.players, owner_id)
        game = await repository.create(
            session, body.mode, identities, body.checkout_mode, owner_user_id=owner_id
        )

    return GameStateDto.from_entity(game)


@router.get("/{game_id}", response_model=GameStateDto)
async def get_game(game_id: str) -> GameStateDto:
    async with database.session_scope() as session:
        game = await repository.get(session, game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="game not found")

    return GameStateDto.from_entity(game)
