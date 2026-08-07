"""Session lifecycle over HTTP.

Only the two calls a device makes *around* the socket live here: creating a game
(there is no game id yet to connect to) and reading its state (initial load,
restore after a refresh, and the check that a shared link still points at a live
game — a 404 says it plainly).

Everything that *changes* a game runs over the WebSocket instead, so one
mutation reaches every device in the room on one path (core/socket.py,
docs/feature/multi-device.md §3).
"""

from fastapi import APIRouter, HTTPException

from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.entity.game import Game
from app.api.features.game.services.game_store import store

router = APIRouter(prefix="/games", tags=["Game"])


@router.post("", response_model=GameStateDto, status_code=201)
def create_game(body: GameConfigDto) -> GameStateDto:
    names = [stripped for name in body.player_names if (stripped := name.strip())]
    if not names:
        raise HTTPException(status_code=422, detail="at least one player is required")
    return GameStateDto.from_entity(store.create(body.mode, names, body.checkout_mode))


@router.get("/{game_id}", response_model=GameStateDto)
def get_game(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    return GameStateDto.from_entity(game)


def _get_game(game_id: str) -> Game:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game
