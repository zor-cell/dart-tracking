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

from app.api.features.auth.services.current_user import CurrentUser
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.persistence.game_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/games", tags=["Game"])


@router.post("", response_model=GameStateDto, status_code=201)
async def create_game(body: GameConfigDto, user: CurrentUser) -> GameStateDto:
    names = [stripped for name in body.player_names if (stripped := name.strip())]
    if not names:
        raise HTTPException(status_code=422, detail="at least one player is required")

    owner_id = user.id if user else None

    async with database.session_scope() as session:
        game = await repository.create(
            session, body.mode, names, body.checkout_mode, owner_user_id=owner_id
        )

    return GameStateDto.from_entity(game)


@router.get("/{game_id}", response_model=GameStateDto)
async def get_game(game_id: str) -> GameStateDto:
    async with database.session_scope() as session:
        game = await repository.get(session, game_id)

    if game is None:
        raise HTTPException(status_code=404, detail="game not found")

    return GameStateDto.from_entity(game)
