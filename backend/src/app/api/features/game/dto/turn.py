from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.entity.turn import Turn


class TurnDto(CamelModel):
    player_id: int
    darts: list[int]
    busted: bool

    @classmethod
    def from_entity(cls, turn: Turn) -> Self:
        return cls(player_id=turn.player_id, darts=list(turn.darts), busted=turn.busted)
