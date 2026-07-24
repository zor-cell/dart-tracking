"""Canonical dartboard geometry.

All radii are in millimetres from the board centre, per the WDF/BDO standard
setup. This is the "board plane" that the homography maps image pixels into:
origin at the bullseye, x to the right, y up, angles measured counter-clockwise
from +x.
"""

import math
from dataclasses import dataclass

# Ring radii (mm from centre). Each pair is inner/outer edge of a ring.
BULLSEYE_RADIUS = 6.35  # the 50
BULL_RADIUS = 15.9  # the 25
TRIPLE_INNER_RADIUS = 99.0
TRIPLE_OUTER_RADIUS = 107.0
DOUBLE_INNER_RADIUS = 162.0
DOUBLE_OUTER_RADIUS = 170.0  # outer edge of scoring area

# Drawn as the overlay, outermost last so it paints on top.
RING_RADII = (
    BULLSEYE_RADIUS,
    BULL_RADIUS,
    TRIPLE_INNER_RADIUS,
    TRIPLE_OUTER_RADIUS,
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
)

SECTOR_COUNT = 20
SECTOR_ANGLE = 2 * math.pi / SECTOR_COUNT  # 18 degrees

# Sector values clockwise starting at 20, which by convention hangs on top.
SECTOR_ORDER = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)

# Sector 20 is centred straight up.
FIRST_SECTOR_CENTRE_ANGLE = math.pi / 2


def sector_centre_angle(index: int) -> float:
    """Angle (radians) of the centre of the sector at `index` in SECTOR_ORDER.

    Sectors run clockwise, so the angle decreases as the index grows.
    """
    return FIRST_SECTOR_CENTRE_ANGLE - index * SECTOR_ANGLE


def sector_boundary_angles() -> list[float]:
    """The 20 wire angles separating adjacent sectors."""
    return [sector_centre_angle(index) + SECTOR_ANGLE / 2 for index in range(SECTOR_COUNT)]


def is_red_sector(index: int) -> bool:
    """Whether the double/triple ring of sector `index` is red rather than green.

    Colours strictly alternate around the board, and sector 20 (index 0) is red.
    Detection relies on this to recover the board's rotation.
    """
    return index % 2 == 0


@dataclass(frozen=True)
class Segment:
    """What a point on the board is worth.

    The bull is modelled as sector value 25 at double, which is how darts
    scoring treats it — a checkout on the bullseye is a double. That keeps
    `points` a plain `value * multiplier` everywhere instead of needing a
    special case per ring.
    """

    value: int  # sector value, 25 for the bull, 0 for a miss
    multiplier: int  # 0 miss, 1 single, 2 double, 3 triple

    @property
    def points(self) -> int:
        return self.value * self.multiplier

    @property
    def label(self) -> str:
        """Short form as it would be called out: T20, D16, S5, BULL, 25, MISS."""
        if self.multiplier == 0:
            return "MISS"
        if self.value == 25:
            return "BULL" if self.multiplier == 2 else "25"
        return f"{'SDT'[self.multiplier - 1]}{self.value}"


MISS = Segment(value=0, multiplier=0)


def segment_at(x: float, y: float) -> Segment:
    """Which segment the board coordinate (mm) falls in.

    This is the last step of scoring: the homography has already turned a pixel
    into millimetres, and from here it is pure geometry against the standard.
    """
    radius = math.hypot(x, y)

    if radius <= BULLSEYE_RADIUS:
        return Segment(value=25, multiplier=2)
    if radius <= BULL_RADIUS:
        return Segment(value=25, multiplier=1)
    if radius > DOUBLE_OUTER_RADIUS:
        return MISS

    # Sectors run clockwise from 20 at the top, so the angle decreases as the
    # index grows — the same relation `sector_centre_angle` encodes, inverted.
    index = round((FIRST_SECTOR_CENTRE_ANGLE - math.atan2(y, x)) / SECTOR_ANGLE)
    value = SECTOR_ORDER[index % SECTOR_COUNT]

    if TRIPLE_INNER_RADIUS <= radius <= TRIPLE_OUTER_RADIUS:
        return Segment(value=value, multiplier=3)
    if DOUBLE_INNER_RADIUS <= radius <= DOUBLE_OUTER_RADIUS:
        return Segment(value=value, multiplier=2)
    return Segment(value=value, multiplier=1)
