from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.entity.dart import Dart


class DartDto(CamelModel):
    points: int
    # Called-out form ("T20"), so the client displays what was thrown without
    # having to reconstruct it from the points.
    label: str

    @classmethod
    def from_entity(cls, dart: Dart) -> Self:
        return cls(points=dart.points, label=dart.label)
