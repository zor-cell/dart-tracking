from fastapi import APIRouter, HTTPException

from app.api.core.services.game_hub import hub
from app.api.features.game.dto.game_config import GameConfigDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_state_message import GameStateMessage
from app.api.features.game.dto.register_dart import RegisterDartDto
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


@router.post("/{game_id}/darts", response_model=GameStateDto)
async def register_dart(game_id: str, body: RegisterDartDto) -> GameStateDto:
    game = _get_game(game_id)

    game.register_dart(body.to_entity())
    return await _publish(game)


@router.post("/{game_id}/undo", response_model=GameStateDto)
async def undo(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    game.undo()
    return await _publish(game)


@router.post("/{game_id}/next-player", response_model=GameStateDto)
async def next_player(game_id: str) -> GameStateDto:
    game = _get_game(game_id)

    game.next_player()
    return await _publish(game)


async def _publish(game: Game) -> GameStateDto:
    """Push the new state to every device in the game's room and hand it back for
    the caller's own response.

    Two paths carrying the same state is what makes the snapshot's `revision`
    necessary. It goes away once these mutations move onto the socket
    (docs/feature/multi-device.md §3); until then a scoreboard would miss every
    manually entered dart without this.
    """
    state = GameStateDto.from_entity(game)
    await hub.broadcast(game.id, GameStateMessage(state=state))
    return state


def _get_game(game_id: str) -> Game:
    game = store.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game
