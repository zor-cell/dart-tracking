from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.dart import Dart


class DartDto(CamelModel):
    points: int
    # Called-out form ("T20"), so the client displays what was thrown without
    # having to reconstruct it from the points.
    label: str
    # [x, y] in board millimetres, or None for a manually entered dart.
    position: list[float] | None = None

    @classmethod
    def from_entity(cls, dart: Dart) -> Self:
        return cls(
            points=dart.points,
            label=dart.label,
            position=list(dart.position) if dart.position is not None else None,
        )
