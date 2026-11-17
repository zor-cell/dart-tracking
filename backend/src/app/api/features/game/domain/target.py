"""The field a dart was thrown at, where the game names one."""

from dataclasses import dataclass

from app.api.features.calibration.domain.board_geometry import Segment, distance_to_segment

# Scores one dart can finish in double out, as the field that does it.
_BULL_FINISH = 50
_HIGHEST_DOUBLE = 40


@dataclass(frozen=True)
class Target:
    value: int  # sector value, 25 for the bull
    # The ring that counts, 2 or 3; 1 the single; None takes any ring of the number.
    multiplier: int | None

    def hit_by(self, value: int, multiplier: int) -> bool:
        if value != self.value or multiplier == 0:
            return False
        return self.multiplier is None or multiplier == self.multiplier

    def distance(self, x: float, y: float) -> float:
        """Shortest distance (mm) from a tip to where the target counts, 0 inside it."""
        rings = (1, 2) if self.value == 25 else (1, 2, 3)
        wanted = rings if self.multiplier is None else (self.multiplier,)
        return min(distance_to_segment(x, y, Segment(self.value, ring)) for ring in wanted)


def finishing_double(remaining: int) -> Target | None:
    """The double that finishes `remaining` with one dart; None if none does."""
    if remaining == _BULL_FINISH:
        return Target(25, 2)
    if 2 <= remaining <= _HIGHEST_DOUBLE and remaining % 2 == 0:
        return Target(remaining // 2, 2)
    return None
