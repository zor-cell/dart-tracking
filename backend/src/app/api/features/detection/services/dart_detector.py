"""Locate the dart that appeared between two frames and score it: register the frame
onto the reference from board features, difference and clean up, fuse the fragments
into one dart, check its size, take the tip opposite the flight and map it to a segment.
"""

import math

import cv2
import numpy as np

from app.api.features.calibration.domain.board_geometry import (
    DOUBLE_OUTER_RADIUS,
    MISS,
    segment_at,
    single_bed_centres,
)
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.camera_angle import outward_direction
from app.api.features.detection.domain.change_region import ChangeRegion
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.debug.trace import DetectionTrace

# Radius a change must reach to count as a throw at all. Past the scoring area,
# so a dart in the surround is still found and reported as a miss.
_DETECTION_RADIUS_MM = 225.0

# How far past that radius a change may extend once it qualifies. Covers the
# flight of a dart high on the board, which hangs out over the surround.
_SEARCH_MARGIN_MM = 90.0

# ORB features for registration, and how many must survive RANSAC.
_ORB_FEATURES = 4000
_MIN_ALIGNMENT_INLIERS = 40
_RANSAC_REPROJECTION_PX = 2.0

# Per-pixel difference counting as changed, in grey levels.
_DIFFERENCE_THRESHOLD = 40

# Saturation change counted where the board is at least this fraction of the way
# from the black beds to the cream ones.
_SATURATION_THRESHOLD = 30
_SATURATION_BED_LEVEL = 0.6

# Blur applied to the reference before its brightness gates that channel, so a
# wire acts over its own neighbourhood instead of at one pixel.
_BED_BLUR_MM = 3.0

# Contrast the two bed classes must show before their levels are trusted to
# anchor the scale; below it the saturation channel stays off.
_MIN_BED_CONTRAST = 30.0

# Sizes in millimetres on the board, converted to pixels per frame from the
# homography, so one set of numbers holds at any camera distance.
_CLOSE_KERNEL_MM = 3.0  # bridges the gaps in a dart's broken silhouette
_MIN_DART_AREA_MM2 = 20.0  # smallest fused blob still called a dart

# How far off the fitted line a fragment's centroid may sit and still be fused
# into the same dart.
_FUSION_PERP_TOL_MM = 4.0

# Size a fragment needs to anchor the fit or vote on its direction. Smaller
# fragments still contribute their pixels once the direction is settled.
_MIN_CANDIDATE_AREA_MM2 = 10.0
_MIN_CANDIDATE_AREA_PX = 15.0

# Longest span fused into one dart, between fragment *centroids*: the flight
# stands out of the board plane, so the homography magnifies it.
_MAX_DART_LENGTH_MM = 110.0

# Size past which the fused blob is an obstruction, such as a player fetching
# their darts, rather than a dart.
_MAX_BLOB_LENGTH_MM = 250.0
_MAX_BLOB_AREA_MM2 = 8000.0

# Share of a blob's pixels that must still differ from the empty board for it to
# be an added dart; below it the blob marks where a dart was pulled out.
_MIN_CHANGED_FROM_EMPTY = 0.25

# Smallest blob that may be booked as a MISS. Below it, a tip outside the scoring
# area is taken for a registration residual on the surround, not a dart.
_MIN_MISS_AREA_MM2 = 400.0

# Smallest component kept, as a board area and as a pixel floor.
_MIN_SPECKLE_AREA_MM2 = 3.0
_MIN_SPECKLE_AREA_PX = 4.0

# Band at the axis end over which the tip's sideways position is averaged. Does
# not affect how far out the tip sits — that is always the axis extreme.
_TIP_SPAN_MM = 4.0

# Band at each axis end used to measure its width; the wider end is the flight
# when the camera geometry cannot tell.
_FLIGHT_SPAN_MM = 12.0

# The camera geometry orients the dart when height off the board shows in the image
# at this many px per in-plane px, and the axis runs at least this close to it (cos).
_MIN_HEIGHT_VISIBILITY = 0.3
_MIN_AXIS_ALIGNMENT = 0.5

# How far the warp's valid area is pulled in from its own edge, in pixels.
_WARP_MARGIN_PX = 3

# How far a fragment may lie outside the trigger's change box and still count, in mm.
_CHANGE_MARGIN_MM = 15.0

trace = DetectionTrace()


def detect_dart(
    reference: np.ndarray,
    frame: np.ndarray,
    calibration: Calibration,
    empty_board: np.ndarray | None = None,
    change: ChangeRegion | None = None,
) -> Dart | DetectionFailure:
    """Find the dart added in `frame` relative to `reference`, whose calibration it is;
    `empty_board` tells an added dart from a pulled one, `change` where the trigger saw it land.
    """
    global trace
    trace = DetectionTrace(reference=reference, frame=frame)

    pixels_per_mm = _pixels_per_mm(calibration.homography)
    trace.pixels_per_mm = pixels_per_mm
    trace.minimum_speckle_px = _minimum_area(
        _MIN_SPECKLE_AREA_MM2, _MIN_SPECKLE_AREA_PX, pixels_per_mm
    )
    trace.minimum_candidate_px = _minimum_area(
        _MIN_CANDIDATE_AREA_MM2, _MIN_CANDIDATE_AREA_PX, pixels_per_mm
    )

    region_outline = _board_outline(calibration.homography, _DETECTION_RADIUS_MM)
    search_outline = _board_outline(
        calibration.homography, _DETECTION_RADIUS_MM + _SEARCH_MARGIN_MM
    )
    region = _board_region(region_outline, reference.shape)
    search = _board_region(search_outline, reference.shape)
    trace.region, trace.search = region, search
    trace.region_outline, trace.search_outline = region_outline, search_outline
    trace.region_clipped = _outside_image(region_outline, reference.shape)

    # Registration uses the board region only.
    alignment, inliers = _align(frame, reference, region)
    trace.alignment, trace.alignment_inliers = alignment, inliers
    if alignment is None:
        return _record_failure(DetectionFailure.ALIGNMENT_FAILED)

    aligned = cv2.warpPerspective(frame, alignment, reference.shape[1::-1])
    trace.aligned = aligned

    trace.alignment_shift_px = _alignment_shift(alignment, region_outline)

    observed = _warp_coverage(frame.shape, alignment, reference.shape)
    search = cv2.bitwise_and(search, observed)
    trace.observed, trace.search = observed, search
    trace.unobserved_region = cv2.subtract(region, observed)

    mask = _change_mask(
        reference, aligned, calibration.homography, region, search, pixels_per_mm
    )
    trace.change_mask = mask

    if change is not None:
        trace.change_box = _change_box(change, frame.shape, alignment, pixels_per_mm)
    blob = _fuse_dart_fragments(mask, trace.difference, pixels_per_mm, trace.change_box)
    if blob is None:
        return _record_failure(DetectionFailure.NO_CHANGE)

    trace.blob = blob
    _measure_blob(blob, pixels_per_mm)
    if trace.dart_length_mm > _MAX_BLOB_LENGTH_MM or trace.dart_area_mm2 > _MAX_BLOB_AREA_MM2:
        return _record_failure(DetectionFailure.IMPLAUSIBLE_SHAPE)

    if empty_board is not None:
        trace.changed_from_empty = _changed_from_empty(blob, aligned, empty_board)
        if trace.changed_from_empty < _MIN_CHANGED_FROM_EMPTY:
            return _record_failure(DetectionFailure.DARTS_REMOVED)

    centre = _to_board(calibration.homography, tuple(blob.mean(axis=0)))
    outward = outward_direction(calibration, *centre)
    tip, far_end = _tip_and_far_end(blob, pixels_per_mm, outward)
    trace.anchor_to_tip_mm = _anchor_distance(tip, pixels_per_mm)
    board_point = _to_board(calibration.homography, tip)
    segment = segment_at(*board_point, calibration.rings)
    if segment == MISS and trace.dart_area_mm2 < _MIN_MISS_AREA_MM2:
        trace.rejected_miss = True
        return _record_failure(DetectionFailure.NO_CHANGE)

    return Dart(
        tip_image=tip,
        axis_image=(tip, far_end),
        tip_board=board_point,
        segment=segment,
    )


def darts_pulled(
    blobs: list[np.ndarray], aligned: np.ndarray, empty_board: np.ndarray
) -> bool:
    """Whether every located dart's pixels in `aligned` look like the empty board again."""
    return bool(blobs) and all(
        _changed_from_empty(blob, aligned, empty_board) < _MIN_CHANGED_FROM_EMPTY
        for blob in blobs
    )


def _changed_from_empty(
    blob: np.ndarray, aligned: np.ndarray, empty_board: np.ndarray
) -> float:
    """Share of the blob's pixels (x, y) where the frame still differs from the empty board."""
    columns, rows = blob[:, 0].astype(int), blob[:, 1].astype(int)
    difference = cv2.absdiff(aligned, empty_board).max(axis=2)
    return float((difference[rows, columns] > _DIFFERENCE_THRESHOLD).mean())


def _anchor_distance(tip: tuple[float, float], pixels_per_mm: float) -> float:
    """How far the scored tip ended up from the fragment the fit anchored on, in mm.

    Large means the anchor was not part of the dart that was scored.
    """
    anchor = trace.fitted_line[0]
    return float(np.linalg.norm(np.array(tip) - anchor)) / pixels_per_mm


def _record_failure(failure: DetectionFailure) -> DetectionFailure:
    """Note which stage gave up, then hand the failure on unchanged."""
    trace.failure = failure
    return failure


def _to_board(homography: np.ndarray, point: tuple[float, float]) -> tuple[float, float]:
    """Image pixel -> board millimetres."""
    mapped = homography @ np.array([point[0], point[1], 1.0])
    return float(mapped[0] / mapped[2]), float(mapped[1] / mapped[2])


def _to_image(homography: np.ndarray, x: float, y: float) -> tuple[float, float]:
    """Board millimetres -> image pixel."""
    mapped = np.linalg.inv(homography) @ np.array([x, y, 1.0])
    return float(mapped[0] / mapped[2]), float(mapped[1] / mapped[2])


def _pixels_per_mm(homography: np.ndarray) -> float:
    """Image scale at the board in px/mm, averaged around the double ring; used only
    to size kernels and area limits.
    """
    centre = np.array(_to_image(homography, 0.0, 0.0))
    distances = [
        math.dist(
            centre,
            _to_image(
                homography,
                DOUBLE_OUTER_RADIUS * math.cos(angle),
                DOUBLE_OUTER_RADIUS * math.sin(angle),
            ),
        )
        for angle in np.linspace(0, 2 * math.pi, 16, endpoint=False)
    ]
    return float(np.mean(distances)) / DOUBLE_OUTER_RADIUS


def _board_outline(homography: np.ndarray, radius_mm: float) -> np.ndarray:
    """The circle of `radius_mm` on the board, mapped into image space as 360 points."""
    return np.array(
        [
            _to_image(homography, radius_mm * math.cos(angle), radius_mm * math.sin(angle))
            for angle in np.linspace(0, 2 * math.pi, 360, endpoint=False)
        ]
    )


def _board_region(outline: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """A filled mask of everything inside `outline`, in image space."""
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [outline.astype(np.int32)], 255)
    return mask


def _outside_image(outline: np.ndarray, shape: tuple[int, ...]) -> float:
    """Fraction of an outline's points that fall outside the frame."""
    height, width = shape[:2]
    inside = (
        (outline[:, 0] >= 0)
        & (outline[:, 0] < width)
        & (outline[:, 1] >= 0)
        & (outline[:, 1] < height)
    )
    return 1.0 - float(inside.mean())


def _alignment_shift(alignment: np.ndarray, outline: np.ndarray) -> float:
    """How far the camera moved, in pixels, averaged over the board outline."""
    points = np.hstack([outline, np.ones((len(outline), 1))]).T
    mapped = alignment @ points
    w = np.where(np.abs(mapped[2]) < 1e-9, 1e-9, mapped[2])
    moved = np.column_stack((mapped[0] / w, mapped[1] / w))
    return float(np.linalg.norm(moved - outline, axis=1).mean())


def _warp_coverage(
    frame_shape: tuple[int, ...], alignment: np.ndarray, reference_shape: tuple[int, ...]
) -> np.ndarray:
    """Which reference pixels the warped frame actually observed: a white image warped
    the same way, eroded by `_WARP_MARGIN_PX`.
    """
    covered = cv2.warpPerspective(
        np.full(frame_shape[:2], 255, dtype=np.uint8), alignment, reference_shape[1::-1]
    )
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * _WARP_MARGIN_PX + 1, 2 * _WARP_MARGIN_PX + 1)
    )
    return cv2.erode(covered, kernel)


def _align(
    frame: np.ndarray, reference: np.ndarray, region: np.ndarray
) -> tuple[np.ndarray | None, int]:
    """Homography warping `frame` onto `reference`, from ORB features on the board
    with RANSAC.
    """
    orb = cv2.ORB_create(_ORB_FEATURES)
    frame_keypoints, frame_descriptors = orb.detectAndCompute(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), region
    )
    reference_keypoints, reference_descriptors = orb.detectAndCompute(
        cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), region
    )
    if frame_descriptors is None or reference_descriptors is None:
        return None, 0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(frame_descriptors, reference_descriptors)
    if len(matches) < _MIN_ALIGNMENT_INLIERS:
        return None, len(matches)

    source = np.float32([frame_keypoints[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    target = np.float32([reference_keypoints[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    homography, inlier_mask = cv2.findHomography(
        source, target, cv2.RANSAC, _RANSAC_REPROJECTION_PX
    )
    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    if homography is None or inliers < _MIN_ALIGNMENT_INLIERS:
        return None, inliers
    return homography, inliers


def _bed_level(
    brightness: np.ndarray, homography: np.ndarray, points: list[tuple[float, float]]
) -> float | None:
    """Median brightness of the board points in `points`, or None if none are in shot."""
    height, width = brightness.shape[:2]
    values = []
    for x, y in points:
        column, row = (int(round(v)) for v in _to_image(homography, x, y))
        if 0 <= column < width and 0 <= row < height:
            values.append(brightness[row, column])
    return float(np.median(values)) if values else None


def _saturation_thresholds(
    reference: np.ndarray, homography: np.ndarray, pixels_per_mm: float
) -> np.ndarray:
    """Per-pixel threshold on the saturation difference, finite only on light beds
    read off the board through the homography.
    """
    size = _odd_size(_BED_BLUR_MM, pixels_per_mm)
    brightness = cv2.GaussianBlur(reference.max(axis=2).astype(np.float32), (size, size), 0)
    off = np.full(brightness.shape, 255.0, np.float32)

    black_points, cream_points = single_bed_centres()
    black = _bed_level(brightness, homography, black_points)
    cream = _bed_level(brightness, homography, cream_points)
    if black is None or cream is None or cream - black < _MIN_BED_CONTRAST:
        return off

    level = (brightness - black) / (cream - black)
    thresholds = np.where(level > _SATURATION_BED_LEVEL, float(_SATURATION_THRESHOLD), off)
    # Blurred so the channel fades in across a bed edge rather than switching on
    # at one, which would put a step in the mask along every wire.
    return cv2.GaussianBlur(thresholds, (size, size), 0)


def _over(difference: np.ndarray, threshold: np.ndarray | float) -> np.ndarray:
    """Binary mask of the pixels above a threshold, per-pixel or flat."""
    return (difference > threshold).astype(np.uint8) * 255


def _saturation(image: np.ndarray) -> np.ndarray:
    """The HSV saturation channel of a BGR image."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]


def _change_mask(
    reference: np.ndarray,
    aligned: np.ndarray,
    homography: np.ndarray,
    region: np.ndarray,
    search: np.ndarray,
    pixels_per_mm: float,
) -> np.ndarray:
    """Binary mask of what the throw added, in and around the board region, from the
    per-channel maximum difference plus saturation on light beds.
    """
    difference = cv2.absdiff(reference, aligned).max(axis=2)
    trace.difference = difference

    saturation = cv2.absdiff(_saturation(reference), _saturation(aligned))
    thresholds = _saturation_thresholds(reference, homography, pixels_per_mm)

    intensity = _over(difference, _DIFFERENCE_THRESHOLD)
    mask = cv2.bitwise_and(cv2.bitwise_or(intensity, _over(saturation, thresholds)), search)
    trace.raw_mask = mask
    trace.saturation_only = cv2.subtract(mask, intensity)

    # Speckle removal first, then the closing that joins the dart's pieces.
    despeckled = _drop_speckle(mask, pixels_per_mm)
    trace.speckle_removed = cv2.subtract(mask, despeckled)

    closed = cv2.morphologyEx(
        despeckled, cv2.MORPH_CLOSE, _kernel(_CLOSE_KERNEL_MM, pixels_per_mm)
    )

    # Anchor to the board only once each component is whole.
    anchored = _drop_unanchored(closed, region, pixels_per_mm)
    trace.outside_removed = cv2.subtract(closed, anchored)
    return anchored


def _minimum_area(area_mm2: float, area_px: float, pixels_per_mm: float) -> float:
    """An area floor in pixels: the board-relative limit, but never below `area_px`."""
    return max(area_mm2 * pixels_per_mm**2, area_px)


def _drop_speckle(mask: np.ndarray, pixels_per_mm: float) -> np.ndarray:
    """Remove components too small to be part of a dart."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    minimum_area = _minimum_area(_MIN_SPECKLE_AREA_MM2, _MIN_SPECKLE_AREA_PX, pixels_per_mm)
    kept = [
        label for label in range(1, count) if stats[label, cv2.CC_STAT_AREA] >= minimum_area
    ]
    if not kept:
        return np.zeros_like(mask)
    return np.isin(labels, kept).astype(np.uint8) * 255


def _drop_unanchored(mask: np.ndarray, region: np.ndarray, pixels_per_mm: float) -> np.ndarray:
    """Keep, whole, the components that reach into `region` or lie within a dart's
    length of one that does.
    """
    count, labels, _, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return mask

    touching = np.unique(labels[region > 0])
    seeded = [label for label in touching if label != 0]
    if not seeded:
        return np.zeros_like(mask)

    # Distance from every pixel to the nearest anchored component, so a
    # candidate's closest approach is a single min() over its own pixels.
    seeded_mask = np.isin(labels, seeded)
    distance = cv2.distanceTransform(
        (~seeded_mask).astype(np.uint8) * 255, cv2.DIST_L2, cv2.DIST_MASK_PRECISE
    )
    reach = _MAX_DART_LENGTH_MM * pixels_per_mm

    kept = set(seeded)
    for label in range(1, count):
        if label in kept:
            continue
        if distance[labels == label].min() <= reach:
            kept.add(label)
    return np.isin(labels, list(kept)).astype(np.uint8) * 255


def _odd_size(size_mm: float, pixels_per_mm: float) -> int:
    """A kernel edge length in pixels for a size on the board: odd, at least 3."""
    return max(3, int(round(size_mm * pixels_per_mm)) | 1)


def _kernel(size_mm: float, pixels_per_mm: float) -> np.ndarray:
    """An elliptical structuring element of a given size on the board."""
    return cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (_odd_size(size_mm, pixels_per_mm),) * 2
    )


def _fragment_geometry(
    pixels: np.ndarray, difference: np.ndarray
) -> tuple[np.ndarray, float, float]:
    """A fragment's centroid, width across its own principal axis and mean difference
    brightness.
    """
    centre = pixels.mean(axis=0)
    centred = pixels - centre
    if len(pixels) >= 2:
        _, eigenvectors = cv2.PCACompute(pixels, mean=None, maxComponents=1)
        axis = eigenvectors[0]
    else:
        axis = np.array([1.0, 0.0])
    perpendicular = np.linalg.norm(centred - np.outer(centred @ axis, axis), axis=1)
    width = float(np.percentile(perpendicular, 95)) if len(pixels) else 0.0
    columns, rows = pixels[:, 0].astype(int), pixels[:, 1].astype(int)
    brightness = float(difference[rows, columns].mean())
    return centre, width, brightness


def _change_box(
    change: ChangeRegion,
    frame_shape: tuple[int, ...],
    alignment: np.ndarray,
    pixels_per_mm: float,
) -> tuple[float, float, float, float]:
    """The trigger's change box carried onto the reference and widened by the margin."""
    corners = cv2.perspectiveTransform(change.corners(frame_shape[1], frame_shape[0]), alignment)
    margin = _CHANGE_MARGIN_MM * pixels_per_mm
    (left, top), (right, bottom) = corners.reshape(-1, 2).min(axis=0), corners.reshape(-1, 2).max(axis=0)
    return (left - margin, top - margin, right + margin, bottom + margin)


def _fuse_dart_fragments(
    mask: np.ndarray,
    difference: np.ndarray,
    pixels_per_mm: float,
    change_box: tuple[float, float, float, float] | None = None,
) -> np.ndarray | None:
    """Gather the dart's fragments into one set of pixels: anchor on the widest (the
    flight) and keep the line through it most candidate fragments vote for, with
    every fragment on that line contributing its pixels. Only fragments inside
    `change_box` count, unless no candidate lies inside it.
    """
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    trace.labels = labels
    fragments = list(range(1, count))
    if not fragments:
        return None

    minimum_area = _minimum_area(
        _MIN_CANDIDATE_AREA_MM2, _MIN_CANDIDATE_AREA_PX, pixels_per_mm
    )
    candidates = [
        label for label in fragments if stats[label, cv2.CC_STAT_AREA] >= minimum_area
    ]
    if not candidates:
        return None

    if change_box is not None:
        left, top, right, bottom = change_box
        inside = {
            label
            for label in fragments
            if left <= centroids[label][0] <= right and top <= centroids[label][1] <= bottom
        }
        if inside & set(candidates):
            trace.outside_change_fragments = sum(label not in inside for label in candidates)
            fragments = [label for label in fragments if label in inside]
            candidates = [label for label in candidates if label in inside]

    pixels = {
        label: np.column_stack(np.where(labels == label)[::-1]).astype(np.float64)
        for label in fragments
    }
    geometry = {label: _fragment_geometry(pixels[label], difference) for label in fragments}

    # Flight = widest candidate (feathers), brightness breaking any tie.
    flight = max(candidates, key=lambda label: (geometry[label][1], geometry[label][2]))
    anchor = geometry[flight][0]
    tolerance = _FUSION_PERP_TOL_MM * pixels_per_mm

    # Only fragments within one dart length of the flight can be part of it.
    reach = _MAX_DART_LENGTH_MM * pixels_per_mm
    eligible = [
        label for label in fragments if np.linalg.norm(geometry[label][0] - anchor) <= reach
    ]
    trace.flight_label = flight
    trace.eligible_labels = eligible

    candidate_set = set(candidates)

    def collinear_support(direction: np.ndarray) -> tuple[list[int], list[int], float]:
        """Who lies on the line: the voters, everyone, and the length the voters cover."""
        normal = np.array([-direction[1], direction[0]])
        supporters = [
            label
            for label in eligible
            if abs((geometry[label][0] - anchor) @ normal) <= tolerance
        ]
        voters = [label for label in supporters if label in candidate_set]
        projections = [(geometry[label][0] - anchor) @ direction for label in voters]
        return voters, supporters, (max(projections) - min(projections)) if projections else 0.0

    # Candidate directions: the flight's own axis, plus flight -> each candidate.
    directions = []
    if len(pixels[flight]) >= 2:
        _, eigenvectors = cv2.PCACompute(pixels[flight], mean=None, maxComponents=1)
        directions.append(eigenvectors[0])
    for label in candidates:
        offset = geometry[label][0] - anchor
        distance = np.linalg.norm(offset)
        if distance > 0:
            directions.append(offset / distance)

    inliers, best_length, best_direction = [flight], -1.0, None
    for direction in directions:
        voters, supporters, length = collinear_support(direction)
        if flight in voters and len(voters) >= 2 and length > best_length:
            inliers, best_length, best_direction = supporters, length, direction

    if best_direction is None and len(pixels[flight]) >= 2:
        # No other candidate agreed, so fall back to the flight's own axis.
        _, eigenvectors = cv2.PCACompute(pixels[flight], mean=None, maxComponents=1)
        best_direction = eigenvectors[0]
        _, inliers, _ = collinear_support(best_direction)

    trace.inlier_labels = inliers
    trace.fitted_line = (anchor, best_direction)

    sizes = [len(pixels[label]) for label in inliers]
    trace.fragment_count = len(inliers)
    trace.largest_fragment_share = max(sizes) / sum(sizes)

    dart = np.vstack([pixels[label] for label in inliers])
    if len(dart) < _MIN_DART_AREA_MM2 * pixels_per_mm**2:
        return None
    return dart


def _measure_blob(points: np.ndarray, pixels_per_mm: float) -> None:
    """Record the fused blob's length, width and area in board millimetres."""
    mean, eigenvectors = cv2.PCACompute(points, mean=None, maxComponents=1)
    axis = eigenvectors[0]
    centred = points - mean
    projections = centred @ axis
    perpendicular = np.linalg.norm(centred - np.outer(projections, axis), axis=1)

    trace.dart_length_mm = float(projections.max() - projections.min()) / pixels_per_mm
    # Doubled: the percentile is a distance from the axis, so it is a half-width.
    trace.dart_width_mm = 2.0 * float(np.percentile(perpendicular, 95)) / pixels_per_mm
    trace.dart_area_mm2 = len(points) / pixels_per_mm**2


def _tip_and_far_end(
    points: np.ndarray, pixels_per_mm: float, outward: np.ndarray | None
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The dart's two ends along its principal axis, tip first. The flight is the end lying
    `outward` (image direction off the board) where that is clear, else the wider end."""
    mean, eigenvectors = cv2.PCACompute(points, mean=None, maxComponents=1)
    axis = eigenvectors[0]
    centred = points - mean
    projections = centred @ axis
    # Perpendicular distance of every pixel from the axis: the width profile.
    widths = np.linalg.norm(centred - np.outer(projections, axis), axis=1)

    ends = []
    end_widths = []
    for extreme in (projections.min(), projections.max()):
        near = np.abs(projections - extreme) <= _TIP_SPAN_MM * pixels_per_mm
        # The end is the extreme along the axis plus the band's mean offset across it.
        offsets = centred[near] - np.outer(projections[near], axis)
        ends.append(mean[0] + axis * extreme + offsets.mean(axis=0))
        # Gauge the end's width over a wider band, robust to a few stray pixels.
        band = np.abs(projections - extreme) <= _FLIGHT_SPAN_MM * pixels_per_mm
        end_widths.append(float(np.percentile(widths[band], 90)))

    flight = int(np.argmax(end_widths))
    trace.oriented_by = "width"
    if outward is not None and np.linalg.norm(outward) / pixels_per_mm >= _MIN_HEIGHT_VISIBILITY:
        along = ends[1] - ends[0]
        alignment = float(along @ outward) / (np.linalg.norm(along) * np.linalg.norm(outward))
        if abs(alignment) >= _MIN_AXIS_ALIGNMENT:
            flight = 1 if alignment > 0 else 0
            trace.oriented_by = "geometry"
    tip, far_end = ends[1 - flight], ends[flight]
    trace.axis_ends = (tip, far_end)
    trace.end_widths = (float(end_widths[1 - flight]), float(end_widths[flight]))
    return tuple(tip), tuple(far_end)
