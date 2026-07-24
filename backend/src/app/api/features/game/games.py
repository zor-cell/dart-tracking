from fastapi import APIRouter, HTTPException

from app.api.features.game.dto.create_game import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.register_dart import RegisterDartDto
from app.api.features.game.entity.game import Game
from app.api.features.game.services.game_store import store

router = APIRouter(prefix="/games", tags=["Game"])


@router.post("", response_model=GameStateDto, status_code=201)
def create_game(body: GameConfigDto) -> GameStateDto:
    names = [stripped for name in body.player_names if (stripped := name.strip())]
    if not names:
        raise HTTPException(status_code=422, detail="at least one player is required")
    return GameStateDto.from_entity(store.create(body.mode, names))


@router.get("/{game_id}", response_model=GameStateDto)
def get_game(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    return GameStateDto.from_entity(game)


@router.post("/{game_id}/darts", response_model=GameStateDto)
def register_dart(game_id: str, body: RegisterDartDto) -> GameStateDto:
    game = _get_game(game_id)

    game.register_dart(body.points)
    return GameStateDto.from_entity(game)


@router.post("/{game_id}/undo", response_model=GameStateDto)
def undo(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    game.undo()
    return GameStateDto.from_entity(game)


@router.post("/{game_id}/next-player", response_model=GameStateDto)
def next_player(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    game.next_player()
    return GameStateDto.from_entity(game)


def _get_game(game_id: str) -> Game:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game
