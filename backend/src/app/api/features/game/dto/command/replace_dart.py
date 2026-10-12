from typing import Literal

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.dart import Dart


class ReplaceDartDto(CamelModel):
    """Client -> server: book a different field for one dart of the open visit.
    The dart keeps its place; the replacement is a manual booking and so carries
    no tip."""

    type: Literal["replace_dart"]
    index: int = Field(ge=0)
    value: int = Field(ge=0, le=25)  # sector value, 25 for the bull, 0 for a miss
    multiplier: int = Field(ge=0, le=3)  # 0 miss, 1 single, 2 double, 3 triple

    def to_entity(self) -> Dart:
        return Dart(value=self.value, multiplier=self.multiplier)
