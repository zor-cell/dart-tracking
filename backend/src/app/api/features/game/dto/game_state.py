from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.player_state import PlayerState


class GameStateResponse(CamelModel):
    id: str
    mode: int
    players: list[PlayerState]
    current_player_index: int
    darts_this_turn: list[int]
    darts_remaining: int
    winner_id: int | None
