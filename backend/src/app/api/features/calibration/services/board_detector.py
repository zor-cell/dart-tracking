"""Automatic dartboard detection.

Pipeline (see docs/roadmap.md §6.1 for the literature this follows):

1. Segment the red and green double/triple segments in HSV. They are by far the
   most distinctive feature of a board and survive poor lighting better than
   edges do.
2. Work out which of those blobs are actually the board, by hypothesising one
   and seeing how many of them agree, then fit an ellipse to the convex hull of
   the winners. This step exists because fitting alone cannot be trusted: a
   hull is an outer envelope, so one stray blob drags the whole fit, and
   red-ish clutter is the norm rather than the exception (furniture, warm
   light, the numbers and branding printed around the board itself). Under
   perspective a circle projects to an ellipse, and the outermost coloured ring
   is the outer edge of the double ring — a known 170 mm radius. Every point on
   the fitted ellipse is therefore the image of a board point at exactly that
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
hangs on top, asked of each candidate's own homography so that a steep viewing
angle does not tilt the answer onto the neighbouring rotation.
"""

import math

import cv2
import numpy as np

from app.api.features.calibration.domain.board_geometry import (
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_ANGLE,
    SECTOR_COUNT,
    TRIPLE_INNER_RADIUS,
    TRIPLE_OUTER_RADIUS,
    is_red_sector,
    sector_boundary_angles,
)
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.debug.trace import CalibrationTrace

# HSV bounds. Red wraps around the hue axis, so it needs two ranges.
_RED_LOWER_1 = np.array([0, 90, 60])
_RED_UPPER_1 = np.array([10, 255, 255])
_RED_LOWER_2 = np.array([170, 90, 60])
_RED_UPPER_2 = np.array([180, 255, 255])
_GREEN_LOWER = np.array([40, 60, 40])
_GREEN_UPPER = np.array([90, 255, 255])

# Cleans the colour masks before components are read off them.
_MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# Angular steps per full turn when walking the ring for colour transitions. Well
# below the 18 degrees between sectors, so each transition is placed precisely.
_RING_WALK_STEPS = 720

# Where colour is sampled along the ray from the board centre out to the ring,
# as a fraction of that ray. Spans both the triple and the double ring; samples
# landing on the black/white singles return no colour and are ignored.
_SAMPLE_FRACTIONS = tuple(np.linspace(0.5, 0.98, 20))

# Wire angles are re-sampled from an improved centre estimate until the centre
# stops moving. The pass cap only bounds a frame that oscillates instead of
# settling.
_CENTRE_CONVERGENCE_PX = 0.5
_MAX_REFINEMENT_PASSES = 6

# Radius at which each ring's segment centroids sit, as a fraction of the double
# ring's outer radius, and how far off it a centroid may sit and still count.
_DOUBLE_BAND = (DOUBLE_INNER_RADIUS + DOUBLE_OUTER_RADIUS) / 2 / DOUBLE_OUTER_RADIUS
_TRIPLE_BAND = (TRIPLE_INNER_RADIUS + TRIPLE_OUTER_RADIUS) / 2 / DOUBLE_OUTER_RADIUS
_BAND_TOLERANCE = 0.10

# Board hypotheses drawn, each an ellipse fitted through 5 sampled centroids.
_RANSAC_ITERATIONS = 800

# Sanity bounds on a candidate ellipse: how elongated it may be, and how much of
# the frame it may span.
_MAX_AXIS_RATIO = 4.0
_MAX_FRAME_SHARE = 1.2

# Structure a candidate must show before its votes count. The minority share is
# what separates a board from the surround it hangs in, whose branding arcs form
# a convincing but single-coloured ring.
_ANGULAR_SECTORS = 12  # bins the ring is divided into to check it is populated
_MIN_ANGULAR_SECTORS = 8  # how many of those bins must be occupied
_MIN_BAND_MEMBERS = 6  # centroids needed per ring band
_MIN_MINORITY_SHARE = 0.25  # smallest share the rarer of red/green may hold

# Centroids beyond this fraction of the current ellipse are trimmed as lying
# outside the double ring, repeated at most this many times.
_OUTER_BAND_LIMIT = 0.99
_MAX_BAND_PASSES = 4

# Smallest mask component treated as a ring segment rather than speckle.
_MIN_COMPONENT_AREA = 20

# What the most recent call to `detect_board` saw at each stage.
trace = CalibrationTrace()


def detect_board(image: np.ndarray) -> Calibration | CalibrationFailure:
    """Locate the board and derive the image -> board homography.

    On failure returns the stage that gave up rather than a bare None, so the
    client can tell the user what to change instead of just that it did not
    work. Every intermediate stage is recorded onto the module-level `trace`
    for inspection.
    """
    global trace
    trace = CalibrationTrace()

    height, width = image.shape[:2]
    red_mask, green_mask = _colour_masks(image)
    combined = cv2.bitwise_or(red_mask, green_mask)
    trace.image, trace.red_mask, trace.green_mask = image, red_mask, green_mask

    selected = _select_board_components(red_mask, green_mask, max(height, width))
    if selected is None:
        return _record_failure(CalibrationFailure.ELLIPSE_FIT_FAILED)
    red_mask, green_mask = selected

    surviving = cv2.bitwise_or(red_mask, green_mask)
    trace.dropped_off_board = cv2.subtract(combined, surviving)

    fitted = _fit_ring_ellipse(red_mask, green_mask)
    if fitted is None:
        return _record_failure(CalibrationFailure.ELLIPSE_FIT_FAILED)
    ellipse, red_mask, green_mask = fitted

    trace.dropped_outer = cv2.subtract(surviving, cv2.bitwise_or(red_mask, green_mask))
    trace.kept_red, trace.kept_green = red_mask, green_mask
    trace.ellipse = ellipse

    # The first pass casts its rays from the ellipse centre, which perspective
    # offsets from the real board centre, so the wire angles come out skewed.
    # Each homography locates the centre better than the last, so re-sampling
    # from it straightens the rays out until the estimate stops moving.
    homography = None
    centre = ellipse[0]

    for _ in range(_MAX_REFINEMENT_PASSES):
        trace.begin_pass(centre)

        correspondences = _match_sector_wires(ellipse, centre, red_mask, green_mask)
        if correspondences is None:
            return _record_failure(CalibrationFailure.SECTOR_WIRES_UNCLEAR)
        trace.current.correspondences = correspondences

        homography = _fit_homography(ellipse, correspondences)
        if homography is None:
            return _record_failure(CalibrationFailure.HOMOGRAPHY_FAILED)
        trace.current.homography = homography

        refined = _project_board_centre(homography)
        trace.current.projected_centre = refined

        shift = math.dist(refined, centre)
        centre = refined
        if shift < _CENTRE_CONVERGENCE_PX:
            break

    return Calibration(homography=homography, image_width=width, image_height=height)


def _record_failure(failure: CalibrationFailure) -> CalibrationFailure:
    """Note which stage gave up, then hand the failure on unchanged."""
    trace.failure = failure
    return failure


def _project_to_image(inverse: np.ndarray, x: float, y: float) -> tuple[float, float]:
    """Where a board coordinate (mm) lands in the image, given inv(homography)."""
    point = inverse @ np.array([x, y, 1.0])
    return float(point[0] / point[2]), float(point[1] / point[2])


def _project_board_centre(homography: np.ndarray) -> tuple[float, float]:
    """Where the board centre (the bull) lands in the image."""
    return _project_to_image(np.linalg.inv(homography), 0.0, 0.0)


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
    trace.hull = hull
    if len(hull) < 5:
        return None

    return cv2.fitEllipse(hull)


def _components(
    mask: np.ndarray,
) -> tuple[np.ndarray, list[tuple[int, tuple[float, float], int]]]:
    """Label a mask and list its components as (label, centroid, area)."""
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    found = [
        (
            label,
            (float(centroids[label][0]), float(centroids[label][1])),
            int(stats[label, cv2.CC_STAT_AREA]),
        )
        for label in range(1, count)  # label 0 is the background
        if stats[label, cv2.CC_STAT_AREA] >= _MIN_COMPONENT_AREA
    ]
    return labels, found


def _keep_labels(labels: np.ndarray, kept: set[int]) -> np.ndarray:
    """Rebuild a mask from the labels that survived a filter."""
    if not kept:
        return np.zeros(labels.shape, dtype=np.uint8)
    return np.isin(labels, list(kept)).astype(np.uint8) * 255


def _select_board_components(
    red: np.ndarray, green: np.ndarray, frame: int
) -> tuple[np.ndarray, np.ndarray] | None:
    """Keep only the components that agree on one board.

    Fitting cannot be trusted here: an ellipse fitted through everything is
    dragged by whatever coloured clutter happens to be in shot, because in a
    least-squares fit every point pulls and none can be ignored. So the board is
    *hypothesised* instead draw five component centroids, fit an ellipse
    through them, and count how many of the remaining centroids that ellipse
    explains. Outliers never have to be identified up front; they simply fail to
    vote. Whatever backed the best hypothesis is the board.

    What makes this work where plain ellipse RANSAC does not is the strength of
    the model being tested. "Points lie on this ellipse" is far too weak the
    triple ring offers nearly as many points as the double ring, so degenerate
    slivers grazing both outscore the truth. A candidate here has to explain a
    whole *board*: two concentric rings at the ratio the standard fixes, each
    running the full way round, each alternating red and green. Voting per
    component rather than per pixel matters too, or the fatter triple segments
    would outweigh the double ring they are supposed to corroborate.

    Returns None when nothing convincing was found, which is a better answer
    than a confident fit to a chair.
    """
    red_labels, red_found = _components(red)
    green_labels, green_found = _components(green)

    # (centroid, colour, mask index, label) enough to score a candidate and
    # then rebuild the masks from whichever entries backed it.
    entries = [(centroid, 1, 0, label) for label, centroid, _ in red_found] + [
        (centroid, -1, 1, label) for label, centroid, _ in green_found
    ]
    if len(entries) < 5:
        return None

    generator = np.random.default_rng(0)
    points = np.array([entry[0] for entry in entries], dtype=np.float32)

    best_votes: list[int] = []
    best_ellipse = None

    for _ in range(_RANSAC_ITERATIONS):
        sample = points[generator.choice(len(entries), 5, replace=False)]
        try:
            candidate = cv2.fitEllipse(sample)
        except cv2.error:  # five points that do not describe an ellipse
            continue

        votes = _board_votes(candidate, entries, frame)
        if len(votes) > len(best_votes):
            best_votes, best_ellipse = votes, candidate

    if not best_votes:
        return None

    best_votes = _settle_hypothesis(best_ellipse, entries, frame, best_votes)

    kept: tuple[set[int], set[int]] = (set(), set())
    for index in best_votes:
        _, _, mask_index, label = entries[index]
        kept[mask_index].add(label)

    return _keep_labels(red_labels, kept[0]), _keep_labels(green_labels, kept[1])


def _settle_hypothesis(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    entries: list[tuple[tuple[float, float], int, int, int]],
    frame: int,
    votes: list[int],
) -> list[int]:
    """Refit the winning hypothesis on its own voters and collect them again.

    The winner came out of five randomly drawn points, so it is only as good as
    that draw: close enough to out-vote every rival, but off by enough that
    segments near the edge of the tolerance miss out. Those gaps matter later
    a missing double segment is a missing colour transition, and the wire
    matching insists on all twenty. Refitting on the double-ring voters and
    re-collecting recovers them.
    """
    for _ in range(_MAX_BAND_PASSES):
        ring = [
            entries[index][0]
            for index in votes
            if _band_of(ellipse, entries[index][0]) == _DOUBLE_BAND
        ]
        if len(ring) < 5:
            break

        # Fitted through centroids, so it lands mid-ring; scaling it out by the
        # same fraction puts it back on the outer edge the band radii assume.
        centre, (axis_a, axis_b), angle = cv2.fitEllipse(np.array(ring, dtype=np.float32))
        refit = (centre, (axis_a / _DOUBLE_BAND, axis_b / _DOUBLE_BAND), angle)

        settled = _board_votes(refit, entries, frame)
        if len(settled) <= len(votes):
            break
        votes, ellipse = settled, refit

    return votes


def _band_of(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    centroid: tuple[float, float],
) -> float | None:
    """Which ring band this centroid falls in, if any."""
    radius = _normalised_radius(ellipse, centroid)
    for band in (_DOUBLE_BAND, _TRIPLE_BAND):
        if abs(radius - band) < _BAND_TOLERANCE:
            return band
    return None


def _board_votes(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    entries: list[tuple[tuple[float, float], int, int, int]],
    frame: int,
) -> list[int]:
    """Indices of the components this candidate board explains, or none at all.

    Returns an empty list the moment the candidate fails a structural test, so
    an implausible board scores zero rather than a plausible-looking count.
    """
    (_, _), (axis_a, axis_b), _ = ellipse
    if (
        min(axis_a, axis_b) <= 0
        or max(axis_a, axis_b) / min(axis_a, axis_b) > _MAX_AXIS_RATIO
        or max(axis_a, axis_b) > _MAX_FRAME_SHARE * frame
    ):
        return []

    voters: list[int] = []
    sectors: set[int] = set()
    bands: dict[float, list[int]] = {_DOUBLE_BAND: [], _TRIPLE_BAND: []}

    for index, (centroid, colour, _, _) in enumerate(entries):
        local_x, local_y = _unit_circle_point(ellipse, centroid)
        radius = math.hypot(local_x, local_y)

        for band in bands:
            if abs(radius - band) < _BAND_TOLERANCE:
                voters.append(index)
                bands[band].append(colour)
                angle = math.atan2(local_y, local_x) + math.pi
                sectors.add(int(angle / (2 * math.pi) * _ANGULAR_SECTORS) % _ANGULAR_SECTORS)
                break

    #voters have to be distributed across multiple sectors
    if len(sectors) < _MIN_ANGULAR_SECTORS:
        return []

    for members in bands.values():
        #band has to be populated
        if len(members) < _MIN_BAND_MEMBERS:
            return []

        #band alternates between red and green
        minority = min(members.count(1), members.count(-1))
        if minority < _MIN_MINORITY_SHARE * len(members):
            return []

    return voters


def _unit_circle_point(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    point: tuple[float, float],
) -> tuple[float, float]:
    """Point in the ellipse's own frame, scaled so the ellipse is the unit circle.

    Distance from the origin is then directly comparable to the band radii, and
    the angle is the board angle up to the perspective skew.
    """
    (centre_x, centre_y), (axis_a, axis_b), angle_degrees = ellipse
    rotation = math.radians(angle_degrees)
    offset_x, offset_y = point[0] - centre_x, point[1] - centre_y

    return (
        (offset_x * math.cos(rotation) + offset_y * math.sin(rotation)) / (axis_a / 2),
        (-offset_x * math.sin(rotation) + offset_y * math.cos(rotation)) / (axis_b / 2),
    )



def _fit_ring_ellipse(
    red: np.ndarray, green: np.ndarray
) -> tuple[
    tuple[tuple[float, float], tuple[float, float], float], np.ndarray, np.ndarray
] | None:
    """Fit the double ring, discarding whatever still lies outside it.

    Clutter close to the board survives the neighbour test — the numbers around
    the ring and the branding on a surround do have coloured segments nearby —
    but it always sits further out than the double ring does. So: fit, drop
    every component whose centroid falls outside that boundary, refit. The
    first fit is too generous precisely because the strays inflate it, which is
    why one pass is not enough; each round shrinks the ellipse and pushes the
    remainder further out, so the loop converges on the ring.

    Returns the ellipse together with the masks it was fitted to, since
    everything downstream should be reading the cleaned ones.
    """
    ellipse = _fit_outer_ellipse(cv2.bitwise_or(red, green))
    if ellipse is None:
        return None

    for _ in range(_MAX_BAND_PASSES):
        dropped_any = False
        masks = []

        for mask in (red, green):
            labels, found = _components(mask)
            kept = set()
            for label, centroid, _ in found:
                if _normalised_radius(ellipse, centroid) <= _OUTER_BAND_LIMIT:
                    kept.add(label)
                else:
                    dropped_any = True
            masks.append(_keep_labels(labels, kept))

        red, green = masks
        if not dropped_any:
            break

        refit = _fit_outer_ellipse(cv2.bitwise_or(red, green))
        if refit is None:  # keep the last usable fit rather than failing outright
            break
        ellipse = refit

    return ellipse, red, green


def _normalised_radius(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    point: tuple[float, float],
) -> float:
    """Where a point sits relative to the ellipse — 1.0 is exactly on it.

    Rotating the ellipse back onto the axes and dividing by the matching
    semi-axis turns it into the unit circle, which makes the value comparable
    all the way around regardless of how squashed the ellipse is.
    """
    return math.hypot(*_unit_circle_point(ellipse, point))


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
) -> list[tuple[float, float]] | None:
    """Pair each detected colour transition with the board angle of its wire.

    Returns (ellipse_parameter, board_angle) pairs, or None if too few
    transitions were found to trust the result.
    """
    colours = _walk_ring_colours(ellipse, centre, red_mask, green_mask)
    transitions = _find_colour_transitions(colours)

    trace.current.ring_colours = colours
    trace.current.transitions = transitions

    # all sectors have to be found exactly
    if len(transitions) != SECTOR_COUNT:
        return None

    boundaries = sector_boundary_angles()

    # Transitions come out ordered by ellipse parameter. Board angles at the
    # wires decrease as the parameter grows (the two run opposite), so the
    # candidate assignments are the cyclic rotations of that reversed order.
    candidates: list[tuple[int, list[tuple[float, float]]]] = []

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

        candidates.append((agreement, pairs))

    # Colour decides on its own; the upright convention only separates the ten
    # assignments colour cannot tell apart, and never outvotes a wire.
    best_agreement = max(agreement for agreement, _ in candidates)
    tied = [pairs for agreement, pairs in candidates if agreement == best_agreement]
    return min(tied, key=lambda pairs: _upright_penalty(ellipse, pairs))


def _upright_penalty(
    ellipse: tuple[tuple[float, float], tuple[float, float], float],
    pairs: list[tuple[float, float]],
) -> float:
    """How far this assignment tilts the board away from 20 on top.

    Colour alternation repeats every two sectors and so leaves ten equally good
    rotations; this is what picks between them.

    Measured through the assignment's own homography, not off the ellipse
    directly: where a ring point *appears* in the image is not the direction it
    has on the board. Seen from the side the projection swings that apparent
    angle by tens of degrees, while the ten candidates sit only 36 degrees
    apart — enough for the neighbouring rotation to look more upright than the
    right one, which is a whole two sectors of scoring error. The homography is
    what already knows the perspective, so asking it removes the bias instead of
    bounding it.
    """
    homography = _fit_homography(ellipse, pairs)
    if homography is None:
        return math.pi

    inverse = np.linalg.inv(homography)
    centre_x, centre_y = _project_to_image(inverse, 0.0, 0.0)
    # Probed at the ring radius, where the correspondences are, so the direction
    # is read off the fit rather than extrapolated beyond it.
    top_x, top_y = _project_to_image(inverse, 0.0, DOUBLE_OUTER_RADIUS)

    # Straight up in image coordinates (y grows downward) is -pi/2.
    on_screen = math.atan2(top_y - centre_y, top_x - centre_x)
    return abs(_wrap(on_screen + math.pi / 2))


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
