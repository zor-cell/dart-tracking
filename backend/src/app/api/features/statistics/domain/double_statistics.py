"""Darts thrown at one finishing double, and where the located ones landed."""

from collections import Counter
from dataclasses import dataclass, field

from app.api.features.calibration.domain.board_geometry import Segment, distance_to_segment

BULL = 25


@dataclass(frozen=True)
class DoubleThrow:
    """A located dart at a double, in board mm."""

    x: float
    y: float
    hit: bool


@dataclass
class DoubleStatistics:
    value: int  # sector value, 25 for the bull
    attempts: int = 0
    hits: int = 0
    distance: float = 0.0  # summed mm of the located darts from the double, 0 for a hit
    fields: Counter[str] = field(default_factory=Counter)  # called-out label of what was hit
    throws: list[DoubleThrow] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "50" if self.value == BULL else f"D{self.value}"

    @property
    def located(self) -> int:
        return len(self.throws)

    def add(self, hit: bool, scored: str, position: tuple[float, float] | None) -> None:
        self.attempts += 1
        self.fields[scored] += 1
        if hit:
            self.hits += 1
        if position is None:
            return
        x, y = position
        self.throws.append(DoubleThrow(x, y, hit))
        if hit:
            return
        self.distance += distance_to_segment(x, y, Segment(value=self.value, multiplier=2))
