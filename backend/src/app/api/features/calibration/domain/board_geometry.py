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
# Double and treble share one width, measured apex to apex per the WDF spec.
RING_WIDTH = 10.0
TRIPLE_OUTER_RADIUS = 107.4
TRIPLE_INNER_RADIUS = TRIPLE_OUTER_RADIUS - RING_WIDTH
DOUBLE_OUTER_RADIUS = 170.0  # outer edge of scoring area
DOUBLE_INNER_RADIUS = DOUBLE_OUTER_RADIUS - RING_WIDTH


@dataclass(frozen=True)
class RingRadii:
    """Where the triple and double ring of one board lie, in mm from the centre."""

    triple_inner: float = TRIPLE_INNER_RADIUS
    triple_outer: float = TRIPLE_OUTER_RADIUS
    double_inner: float = DOUBLE_INNER_RADIUS
    double_outer: float = DOUBLE_OUTER_RADIUS


STANDARD_RINGS = RingRadii()

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


def single_bed_centres() -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Mid-bed points of every single, split into the black beds and the cream ones.

    Beds alternate with the sectors, the black ones being those whose double and
    triple are red. Two per sector: inside the triple ring and outside it.
    """
    radii = (
        (BULL_RADIUS + TRIPLE_INNER_RADIUS) / 2,
        (TRIPLE_OUTER_RADIUS + DOUBLE_INNER_RADIUS) / 2,
    )
    black: list[tuple[float, float]] = []
    cream: list[tuple[float, float]] = []
    for index in range(SECTOR_COUNT):
        angle = sector_centre_angle(index)
        bed = black if is_red_sector(index) else cream
        bed += [(radius * math.cos(angle), radius * math.sin(angle)) for radius in radii]
    return black, cream


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


def segment_at(x: float, y: float, rings: RingRadii = STANDARD_RINGS) -> Segment:
    """Which segment the board coordinate (mm) falls in.

    This is the last step of scoring: the homography has already turned a pixel
    into millimetres, and from here it is pure geometry against the board's rings.
    """
    radius = math.hypot(x, y)

    if radius <= BULLSEYE_RADIUS:
        return Segment(value=25, multiplier=2)
    if radius <= BULL_RADIUS:
        return Segment(value=25, multiplier=1)
    if radius > rings.double_outer:
        return MISS

    # Sectors run clockwise from 20 at the top, so the angle decreases as the
    # index grows — the same relation `sector_centre_angle` encodes, inverted.
    index = round((FIRST_SECTOR_CENTRE_ANGLE - math.atan2(y, x)) / SECTOR_ANGLE)
    value = SECTOR_ORDER[index % SECTOR_COUNT]

    if rings.triple_inner <= radius <= rings.triple_outer:
        return Segment(value=value, multiplier=3)
    if rings.double_inner <= radius <= rings.double_outer:
        return Segment(value=value, multiplier=2)
    return Segment(value=value, multiplier=1)


def segment_from_label(label: str) -> Segment | None:
    """Parse a label back into a Segment, or None if it is not one.

    The inverse of `Segment.label`, so a written-down segment (ground truth) can
    be compared geometrically and not just as a string.
    """
    label = label.strip().upper()
    if label == "MISS":
        return MISS
    if label == "BULL":
        return Segment(value=25, multiplier=2)
    if label == "25":
        return Segment(value=25, multiplier=1)
    if len(label) < 2 or label[0] not in "SDT" or not label[1:].isdigit():
        return None
    value = int(label[1:])
    if value not in SECTOR_ORDER:
        return None
    return Segment(value=value, multiplier="SDT".index(label[0]) + 1)


def _ring_bounds(multiplier: int) -> list[tuple[float, float]]:
    """The radius ranges (mm) a sector segment of this multiplier occupies.

    A single is two disjoint rings — inside the triple and outside it — hence a
    list rather than one pair.
    """
    if multiplier == 3:
        return [(TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS)]
    if multiplier == 2:
        return [(DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS)]
    return [(BULL_RADIUS, TRIPLE_INNER_RADIUS), (TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS)]


def _distance_to_ray(x: float, y: float, angle: float, r0: float, r1: float) -> float:
    """Distance from a point to the radial edge from `r0` to `r1` at `angle`."""
    ax, ay = r0 * math.cos(angle), r0 * math.sin(angle)
    bx, by = r1 * math.cos(angle), r1 * math.sin(angle)
    dx, dy = bx - ax, by - ay
    t = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)
    t = min(max(t, 0.0), 1.0)
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def _distance_to_annular_sector(
    x: float, y: float, r0: float, r1: float, centre_angle: float
) -> float:
    """Distance from a point to the wedge between `r0` and `r1` around `centre_angle`."""
    radius = math.hypot(x, y)
    offset = (math.atan2(y, x) - centre_angle + math.pi) % (2 * math.pi) - math.pi
    half = SECTOR_ANGLE / 2
    if abs(offset) <= half:
        # Same wedge: only the radius can be off, and at most one side of it.
        return max(r0 - radius, radius - r1, 0.0)
    return _distance_to_ray(x, y, centre_angle + math.copysign(half, offset), r0, r1)


def distance_to_segment(x: float, y: float, segment: Segment) -> float:
    """Shortest distance (mm) from a board coordinate to where `segment` scores.

    Zero if the point already lies in it. This separates a tip that missed by a
    wire's width from one that landed in a different part of the board entirely.
    """
    radius = math.hypot(x, y)

    if segment.multiplier == 0:
        return max(0.0, DOUBLE_OUTER_RADIUS - radius)
    if segment.value == 25:
        if segment.multiplier == 2:
            return max(0.0, radius - BULLSEYE_RADIUS)
        return max(BULLSEYE_RADIUS - radius, radius - BULL_RADIUS, 0.0)

    centre_angle = sector_centre_angle(SECTOR_ORDER.index(segment.value))
    return min(
        _distance_to_annular_sector(x, y, r0, r1, centre_angle)
        for r0, r1 in _ring_bounds(segment.multiplier)
    )
