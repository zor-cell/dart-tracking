from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.turn import Turn
from app.api.features.game.dto.dart import DartDto


class VisitDto(CamelModel):
    player_id: int
    darts: list[DartDto]
    points: int
    busted: bool
    # Points each player still needed after this visit, indexed by player id.
    standings: list[int]

    @classmethod
    def from_entity(cls, turn: Turn, standings: dict[int, int]) -> Self:
        return cls(
            player_id=turn.player_id,
            darts=[DartDto.from_entity(dart) for dart in turn.darts],
            points=0 if turn.busted else turn.points,
            busted=turn.busted,
            standings=[standings[player_id] for player_id in sorted(standings)],
        )
