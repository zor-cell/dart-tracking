from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.player import Player


class PlayerDto(CamelModel):
    id: int
    name: str
    identity_id: str
    remaining: int
    # Points per three darts in this game; None before the first dart.
    average: float | None
    # Points of the last closed visit; None before it.
    last_visit: int | None

    @classmethod
    def from_entity(
        cls, player: Player, remaining: int, average: float | None, last_visit: int | None
    ) -> Self:
        """The figures are passed in because they are properties of the game, not
        of the player alone."""
        return cls(
            id=player.id,
            name=player.name,
            identity_id=player.identity_id,
            remaining=remaining,
            average=None if average is None else round(average, 2),
            last_visit=last_visit,
        )
