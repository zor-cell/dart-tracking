"""Darts thrown at one finishing double, and where the located ones landed."""

import math
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from app.api.features.calibration.domain.board_geometry import (
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_ANGLE,
    SECTOR_ORDER,
    Segment,
    distance_to_segment,
    sector_centre_angle,
)

BULL = 25

# Middle of the double ring, in mm from the centre.
_DOUBLE_MID_RADIUS = (DOUBLE_INNER_RADIUS + DOUBLE_OUTER_RADIUS) / 2


class MissDirection(StrEnum):
    """Which side of a double a dart missed on, seen with the double turned to the top."""

    SHORT = "short"
    LONG = "long"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class DoubleThrow:
    """A located dart at a double, in mm from the double's middle with the double turned
    to the top: `across` to the right, `out` away from the centre. The bull keeps x/y."""

    across: float
    out: float
    hit: bool


@dataclass
class DoubleStatistics:
    value: int  # sector value, 25 for the bull
    attempts: int = 0
    hits: int = 0
    miss_distance: float = 0.0  # summed mm over the located misses
    located_misses: int = 0
    directions: Counter[MissDirection] = field(default_factory=Counter)
    throws: list[DoubleThrow] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "50" if self.value == BULL else f"D{self.value}"

    def add(self, hit: bool, position: tuple[float, float] | None) -> None:
        self.attempts += 1
        if hit:
            self.hits += 1
        if position is None:
            return
        x, y = position
        if self.value == BULL:
            self.throws.append(DoubleThrow(x, y, hit))
        else:
            self.throws.append(self._turned(x, y, hit))
        if hit:
            return
        self.located_misses += 1
        self.miss_distance += distance_to_segment(x, y, Segment(value=self.value, multiplier=2))
        if self.value != BULL and (direction := self._direction(x, y)) is not None:
            self.directions[direction] += 1

    def _offset(self, x: float, y: float) -> float:
        """Angle of the point from the double's centre line, counter-clockwise positive."""
        centre = sector_centre_angle(SECTOR_ORDER.index(self.value))
        return (math.atan2(y, x) - centre + math.pi) % (2 * math.pi) - math.pi

    def _turned(self, x: float, y: float, hit: bool) -> DoubleThrow:
        radius, offset = math.hypot(x, y), self._offset(x, y)
        across = -radius * math.sin(offset)
        return DoubleThrow(across, radius * math.cos(offset) - _DOUBLE_MID_RADIUS, hit)

    def _direction(self, x: float, y: float) -> MissDirection | None:
        """The side the dart left the double by, whichever it overshot further."""
        radius, offset = math.hypot(x, y), self._offset(x, y)
        radial = max(DOUBLE_INNER_RADIUS - radius, radius - DOUBLE_OUTER_RADIUS, 0.0)
        sideways = max(radius * (abs(offset) - SECTOR_ANGLE / 2), 0.0)
        if radial == 0 and sideways == 0:
            return None
        if radial >= sideways:
            return MissDirection.SHORT if radius < DOUBLE_INNER_RADIUS else MissDirection.LONG
        return MissDirection.LEFT if offset > 0 else MissDirection.RIGHT
