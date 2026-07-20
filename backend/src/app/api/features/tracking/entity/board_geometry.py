"""Canonical dartboard geometry.

All radii are in millimetres from the board centre, per the WDF/BDO standard
setup. This is the "board plane" that the homography maps image pixels into:
origin at the bullseye, x to the right, y up, angles measured counter-clockwise
from +x.
"""

import math

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
