from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant


class TurnAnnouncementDto(CamelModel):
    """Server -> announcer: the next visit is ready to be thrown by `player`.
    `remaining` is set in x01 when the visit can finish."""

    type: Literal["turn_announcement"] = "turn_announcement"
    player: str
    remaining: int | None

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        player = game.current_player
        finishable = game.variant is GameVariant.X01 and game.checkout is not None
        return cls(
            player=player.name,
            remaining=game.remaining(player.id) if finishable else None,
        )
