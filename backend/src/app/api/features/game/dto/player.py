from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.player import Player


class PlayerDto(CamelModel):
    id: int
    name: str
    remaining: int

    @classmethod
    def from_entity(cls, player: Player, remaining: int) -> Self:
        """`remaining` is passed in because it is a property of the game, not of
        the player alone."""
        return cls(id=player.id, name=player.name, remaining=remaining)
