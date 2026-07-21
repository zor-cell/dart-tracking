"""Automatic dartboard detection.

Pipeline (see docs/roadmap.md §6.1 for the literature this follows):

1. Segment the red and green double/triple segments in HSV. They are by far the
   most distinctive feature of a board and survive poor lighting better than
   edges do.
2. Fit an ellipse to the convex hull of those coloured pixels. Under
   perspective a circle projects to an ellipse, and the outermost coloured ring
   is the outer edge of the double ring — a known 170 mm radius. Every point on
   that fitted ellipse is therefore the image of a board point at exactly that
   radius; only *which* angle each one corresponds to is still unknown.
3. Recover those angles by walking around the ring and finding the red/green
   transitions. Colours change exactly at the sector wires, whose board angles
   are known, so each transition is a true point correspondence rather than an
   assumed one. This matters: mapping the ellipse parameter straight onto the
   board angle is only valid for parallel projection, and at the steep viewing
   angles this system is built for it puts the board centre tens of millimetres
   off — far more than the 8 mm width of a triple ring.
4. Fit the homography from those correspondences.

Colour alternates every sector, so it fixes the rotation only to within two
sectors; the remaining ambiguity is resolved by the convention that sector 20
hangs on top.
"""

import math

import cv2
import numpy as np

from app.api.features.calibration.entity.board_geometry import (
    DOUBLE_OUTER_RADIUS,
    SECTOR_ANGLE,
    SECTOR_COUNT,
    TRIPLE_INNER_RADIUS,
    is_red_sector,
    sector_boundary_angles,
    sector_centre_angle,
)
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure
from app.api.features.calibration.entity.calibration_trace import CalibrationPass, CalibrationTrace

# HSV bounds. Red wraps around the hue axis, so it needs two ranges.
_RED_LOWER_1 = np.array([0, 90, 60])
_RED_UPPER_1 = np.array([10, 255, 255])
_RED_LOWER_2 = np.array([170, 90, 60])
_RED_UPPER_2 = np.array([180, 255, 255])
_GREEN_LOWER = np.array([40, 60, 40])
_GREEN_UPPER = np.array([90, 255, 255])

_MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# A board that occupies less than this share of the frame is almost certainly a
# misdetection (coloured clutter in the room rather than the board itself).
_MIN_COLOURED_PIXEL_RATIO = 0.00001

# How finely the ring is walked when looking for colour transitions. Well below
# the 18 degrees between sectors so each one is located precisely.
_RING_WALK_STEPS = 720

# Where along the ray from the board centre out to the ring to sample colour.
# The triple and double rings sit from about 0.58 of the way out, and they
# carry the same colour per sector, so a generous span catches both; samples
# landing on the black/white singles simply return no colour and are ignored.
# Perspective stretches this parametrisation, hence the margin at both ends.
_SAMPLE_FRACTIONS = tuple(np.linspace(0.5, 0.98, 20))

# Each pass re-samples the wire angles from a better estimate of the board
# centre, and on synthetic test frames the residual shrinks by roughly a factor
# of three per pass (17.5 -> 6.1 -> 2.1 -> 0.5 mm worst case). Iterating to a
# still centre rather than a fixed count keeps that from being a magic number;
# the cap is only there so a frame that oscillates instead of settling cannot
# spin forever.
_CENTRE_CONVERGENCE_PX = 0.5
_MAX_REFINEMENT_PASSES = 6


def detect_board(
    image: np.ndarray, trace: CalibrationTrace | None = None
) -> Calibration | CalibrationFailure:
    """Locate the board and derive the image -> board homography.

    On failure returns the stage that gave up rather than a bare None, so the
    client can tell the user what to change instead of just that it did not
    work.

    Pass a `trace` to get every intermediate stage back for inspection; see
    scripts/debug_images.py. One is always filled in either way — it holds
    references, not copies — so recording never has to be branched around.
    """
    trace = trace if trace is not None else CalibrationTrace()

    height, width = image.shape[:2]
    red_mask, green_mask = _colour_masks(image)
    combined = cv2.bitwise_or(red_mask, green_mask)
    trace.image, trace.red_mask, trace.green_mask = image, red_mask, green_mask

    #dont need colored region check for now
    #if int(np.count_nonzero(combined)) < _MIN_COLOURED_PIXEL_RATIO * width * height:
    #    return _record_failure(trace, CalibrationFailure.NO_COLOURED_REGION)

    ellipse = _fit_outer_ellipse(combined, trace)
    if ellipse is None:
        return _record_failure(trace, CalibrationFailure.ELLIPSE_FIT_FAILED)
    trace.ellipse = ellipse

    # The first pass casts its rays from the ellipse centre, which perspective
    # offsets from the real board centre, so the wire angles come out skewed.
    # Each homography locates the centre better than the last, so re-sampling
    # from it straightens the rays out until the estimate stops moving.
    homography = None
    centre = ellipse[0]

    for _ in range(_MAX_REFINEMENT_PASSES):
        current = trace.begin_pass(centre)

        correspondences = _match_sector_wires(
            ellipse, centre, red_mask, green_mask, current
        )
        if correspondences is None:
            return _record_failure(trace, CalibrationFailure.SECTOR_WIRES_UNCLEAR)
        current.correspondences = correspondences

        homography = _fit_homography(ellipse, correspondences)
        if homography is None:
            return _record_failure(trace, CalibrationFailure.HOMOGRAPHY_FAILED)
        current.homography = homography

        refined = _project_board_centre(homography)
        current.projected_centre = refined

        shift = math.dist(refined, centre)
        centre = refined
        if shift < _CENTRE_CONVERGENCE_PX:
            break

    return Calibration(homography=homography, image_width=width, image_height=height)


def _record_failure(trace: CalibrationTrace, failure: CalibrationFailure) -> CalibrationFailure:
    """Note which stage gave up, then hand the failure on unchanged."""
    trace.failure = failure
    return failure


def _project_board_centre(homography: np.ndarray) -> tuple[float, float]:
    """Where the board centre (the bull) lands in the image."""
    point = np.linalg.inv(homography) @ np.array([0.0, 0.0, 1.0])
    return float(point[0] / point[2]), float(point[1] / point[2])


def _colour_masks(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Binary masks of the red and green board segments."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    red = cv2.bitwise_or(
        cv2.inRange(hsv, _RED_LOWER_1, _RED_UPPER_1),
        cv2.inRange(hsv, _RED_LOWER_2, _RED_UPPER_2),
    )
    green = cv2.inRange(hsv, _GREEN_LOWER, _GREEN_UPPER)

    # Close the wire gaps between segments, then drop isolated speckle.
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, _MORPH_KERNEL)
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, _MORPH_KERNEL)
    red = cv2.morphologyEx(red, cv2.MORPH_OPEN, _MORPH_KERNEL)
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, _MORPH_KERNEL)

    return red, green


def _fit_outer_ellipse(
    mask: np.ndarray,
    trace: CalibrationTrace | None = None,
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    """Fit an ellipse to the outer boundary of the coloured region.

    The convex hull of all coloured pixels traces the outer edge of the double
    ring: the ring is interrupted by the black/white segments between the
    coloured ones, but the hull bridges those gaps.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    points = np.vstack(contours)
    if len(points) < 5:  # fitEllipse needs at least 5 points
        return None

    hull = cv2.convexHull(points)
    if trace is not None:
        trace.hull = hull
    if len(hull) < 5:
        return None

    return cv2.fitEllipse(hull)


def _ellipse_point(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    parameter: float,
    radius_scale: float = 1.0,
) -> tuple[float, float]:
    """Point on (or inside) the ellipse at the given parameter angle."""
    (centre_x, centre_y), (axis_a, axis_b), angle_degrees = ellipse
    # OpenCV reports full axis lengths; the parametric form needs half-axes.
    semi_a = axis_a / 2 * radius_scale
    semi_b = axis_b / 2 * radius_scale
    rotation = math.radians(angle_degrees)

    local_x = semi_a * math.cos(parameter)
    local_y = semi_b * math.sin(parameter)

    return (
        centre_x + local_x * math.cos(rotation) - local_y * math.sin(rotation),
        centre_y + local_x * math.sin(rotation) + local_y * math.cos(rotation),
    )


def _walk_ring_colours(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    centre: tuple[float, float],
    red_mask: np.ndarray,
    green_mask: np.ndarray,
) -> list[int]:
    """Dominant colour at each step around the ring: +1 red, -1 green, 0 unclear.

    Samples along the straight line from `centre` out to the ring. A homography
    maps lines to lines, so if `centre` is the image of the board centre then
    every point on that line shares one board angle — which is what makes the
    colour transitions land on the true sector wires. Each step votes across
    several distances so a stray sample cannot flip the result.
    """
    height, width = red_mask.shape[:2]
    colours = []

    for step in range(_RING_WALK_STEPS):
        parameter = 2 * math.pi * step / _RING_WALK_STEPS
        outer_x, outer_y = _ellipse_point(ellipse, parameter)
        red_votes = 0
        green_votes = 0

        for fraction in _SAMPLE_FRACTIONS:
            x = centre[0] + fraction * (outer_x - centre[0])
            y = centre[1] + fraction * (outer_y - centre[1])
            pixel_x, pixel_y = int(round(x)), int(round(y))
            if not (0 <= pixel_x < width and 0 <= pixel_y < height):
                continue
            if red_mask[pixel_y, pixel_x]:
                red_votes += 1
            elif green_mask[pixel_y, pixel_x]:
                green_votes += 1

        if red_votes > green_votes:
            colours.append(1)
        elif green_votes > red_votes:
            colours.append(-1)
        else:
            colours.append(0)

    return colours


def _find_colour_transitions(colours: list[int]) -> list[tuple[float, bool]]:
    """Parameter angles where the ring changes colour.

    Returns (parameter, becomes_red) pairs. Runs of "unclear" between two
    colours are bridged by placing the transition at their midpoint, which is
    where the sector wire that caused them actually sits.
    """
    transitions = []

    for step in range(_RING_WALK_STEPS):
        colour = colours[step]
        if colour == 0:
            continue

        # Walk forward to the next decided sample, skipping any unclear run.
        gap = 1
        while gap <= _RING_WALK_STEPS and colours[(step + gap) % _RING_WALK_STEPS] == 0:
            gap += 1
        if gap > _RING_WALK_STEPS:
            break

        next_colour = colours[(step + gap) % _RING_WALK_STEPS]
        if next_colour == colour:
            continue

        midpoint = (step + gap / 2) % _RING_WALK_STEPS
        transitions.append(
            (2 * math.pi * midpoint / _RING_WALK_STEPS, next_colour == 1)
        )

    return _drop_spurious_transitions(transitions)


def _drop_spurious_transitions(
    transitions: list[tuple[float, bool]],
) -> list[tuple[float, bool]]:
    """Remove transition pairs too close together to be real sector wires.

    Wires are a whole sector apart, so anything much nearer is a speck of
    misclassified colour — a highlight, a shadow edge — which always shows up
    as a pair (in and straight back out again). Dropping both members keeps the
    remaining sequence aligned with the real wires.
    """
    survivors = list(transitions)
    minimum_separation = SECTOR_ANGLE / 2

    while len(survivors) > 1:
        gaps = [
            (
                (survivors[(index + 1) % len(survivors)][0] - parameter) % (2 * math.pi),
                index,
            )
            for index, (parameter, _) in enumerate(survivors)
        ]
        smallest, index = min(gaps)
        if smallest >= minimum_separation:
            break
        for offset in sorted([index, (index + 1) % len(survivors)], reverse=True):
            survivors.pop(offset)

    return survivors


def _match_sector_wires(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    centre: tuple[float, float],
    red_mask: np.ndarray,
    green_mask: np.ndarray,
    current: CalibrationPass | None = None,
) -> list[tuple[float, float]] | None:
    """Pair each detected colour transition with the board angle of its wire.

    Returns (ellipse_parameter, board_angle) pairs, or None if too few
    transitions were found to trust the result.
    """
    colours = _walk_ring_colours(ellipse, centre, red_mask, green_mask)
    transitions = _find_colour_transitions(colours)

    # Recorded before the count is checked: a run that finds the wrong number of
    # wires is exactly the one worth looking at, and by then it has nothing else
    # to show for itself.
    if current is not None:
        current.ring_colours = colours
        current.transitions = transitions

    # Wires are matched by counting along the sequence, which only lines up if
    # every one of them was found. A short or long sequence would silently
    # shift the assignment and calibrate the board to the wrong rotation, so it
    # is rejected instead: a failed calibration the user can retry beats scoring
    # every future throw against a board that is one sector out.
    if len(transitions) != SECTOR_COUNT:
        return None

    boundaries = sector_boundary_angles()

    # Transitions come out ordered by ellipse parameter. Board angles at the
    # wires decrease as the parameter grows (the two run opposite), so the
    # candidate assignments are the cyclic rotations of that reversed order.
    best: tuple[float, list[tuple[float, float]]] | None = None

    for offset in range(SECTOR_COUNT):
        pairs = []
        agreement = 0

        for index, (parameter, becomes_red) in enumerate(transitions):
            wire = (offset + index) % SECTOR_COUNT
            board_angle = boundaries[wire]
            pairs.append((parameter, board_angle))

            # Wire `w` separates sector `w-1` (at the higher board angle) from
            # sector `w`. The parameter runs opposite to the board angle, so
            # crossing it moves into sector `w` itself.
            if is_red_sector(wire) == becomes_red:
                agreement += 1

        score = agreement / len(transitions) - 0.01 * _upright_penalty(ellipse, pairs)
        if best is None or score > best[0]:
            best = (score, pairs)

    return best[1] if best else None


def _upright_penalty(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    pairs: list[tuple[float, float]],
) -> float:
    """How far this assignment tilts the board away from 20 on top.

    Colour alternation repeats every two sectors and so leaves ten equally good
    rotations; this is what picks between them.
    """
    (centre_x, centre_y), _, _ = ellipse
    target = sector_centre_angle(0)  # sector 20

    # Find the pair nearest to the 20 and see where it actually lands on screen.
    parameter, board_angle = min(
        pairs, key=lambda pair: abs(_wrap(pair[1] - target))
    )
    x, y = _ellipse_point(ellipse, parameter)

    # Straight up in image coordinates (y grows downward) is -pi/2.
    on_screen = math.atan2(y - centre_y, x - centre_x)
    expected_offset = _wrap(board_angle - target)
    return abs(_wrap(on_screen + math.pi / 2 + expected_offset))


def _wrap(angle: float) -> float:
    """Fold an angle into (-pi, pi]."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


def _fit_homography(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    correspondences: list[tuple[float, float]],
) -> np.ndarray | None:
    """Homography taking image pixels to board millimetres.

    Every correspondence sits on the outer edge of the double ring, whose
    radius is known, so the pairs are exact rather than approximated.
    """
    image_points = []
    board_points = []

    for parameter, board_angle in correspondences:
        image_points.append(_ellipse_point(ellipse, parameter))
        board_points.append(
            (
                DOUBLE_OUTER_RADIUS * math.cos(board_angle),
                DOUBLE_OUTER_RADIUS * math.sin(board_angle),
            )
        )

    homography, _ = cv2.findHomography(
        np.array(image_points, dtype=np.float64),
        np.array(board_points, dtype=np.float64),
        cv2.RANSAC,
    )
    return homography
