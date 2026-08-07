from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.dart import DartDto
from app.api.features.game.entity.turn import Turn


class TurnDto(CamelModel):
    player_id: int
    darts: list[DartDto]
    busted: bool

    @classmethod
    def from_entity(cls, turn: Turn) -> Self:
        return cls(
            player_id=turn.player_id,
            darts=[DartDto.from_entity(dart) for dart in turn.darts],
            busted=turn.busted,
        )
