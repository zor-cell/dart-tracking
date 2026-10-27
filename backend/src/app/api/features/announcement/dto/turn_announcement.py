from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant


class TurnAnnouncementDto(CamelModel):
    """Server -> announcer: the next visit is ready to be thrown by `player`.
    `score` is the number the scoreboard shows for them."""

    type: Literal["turn_announcement"] = "turn_announcement"
    player: str
    score: int

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        player = game.current_player
        remaining = game.remaining(player.id)
        return cls(
            player=player.name,
            score=remaining if game.variant is GameVariant.X01 else game.mode - remaining,
        )
