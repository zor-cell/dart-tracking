from fastapi import APIRouter, HTTPException

from app.api.features.game.dto.create_game import CreateGameRequest
from app.api.features.game.dto.game_state import GameStateResponse
from app.api.features.game.dto.register_dart import RegisterDartRequest
from app.api.features.game.entity.game import ALLOWED_MODES
from app.api.features.game.services import store
from app.api.features.game.services.store import to_response

router = APIRouter(prefix="/games", tags=["Game"])


@router.post("", response_model=GameStateResponse, status_code=201)
def create_game(body: CreateGameRequest) -> GameStateResponse:
    if body.mode not in ALLOWED_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {ALLOWED_MODES}")
    names = [name for name in body.player_names if name.strip()]
    if not names:
        raise HTTPException(status_code=422, detail="at least one player is required")
    return to_response(store.create(body.mode, names))


@router.get("/{game_id}", response_model=GameStateResponse)
def get_game(game_id: str) -> GameStateResponse:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return to_response(game)


@router.post("/{game_id}/darts", response_model=GameStateResponse)
def register_dart(game_id: str, body: RegisterDartRequest) -> GameStateResponse:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    game.register_dart(body.points)
    return to_response(game)


@router.post("/{game_id}/next-player", response_model=GameStateResponse)
def next_player(game_id: str) -> GameStateResponse:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    game.next_player()
    return to_response(game)
