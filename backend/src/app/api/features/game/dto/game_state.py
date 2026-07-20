from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.player import PlayerDto
from app.api.features.game.dto.turn import TurnDto
from app.api.features.game.entity.game import Game
from app.api.features.game.entity.game_mode import GameMode


class GameStateDto(CamelModel):
    id: str
    mode: GameMode
    players: list[PlayerDto]
    current_player_index: int
    turns: list[TurnDto]
    darts_remaining: int
    winner_id: int | None

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        return cls(
            id=game.id,
            mode=game.mode,
            players=[
                PlayerDto.from_entity(player, game.remaining(player.id))
                for player in game.players
            ],
            current_player_index=game.current_player_index,
            turns=[TurnDto.from_entity(turn) for turn in game.turns],
            darts_remaining=game.darts_remaining,
            winner_id=game.winner.id if game.winner is not None else None,
        )
