from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.player_dto import PlayerDto


class GameStateDto(CamelModel):
    id: str
    mode: int
    players: list[PlayerDto]
    current_player_index: int
    darts_this_turn: list[int]
    darts_remaining: int
    winner_id: int | None
