"""Locate the dart that appeared between two frames, and score it.

Pipeline:

1. Register the incoming frame onto the reference frame, using ORB features
   restricted to the board. Handheld cameras drift, and a drift of even a few
   pixels swamps a dart: measured on the test set, an unregistered difference
   across a 25 px camera shift lights up ~117 000 pixels where the dart itself
   is worth a few hundred. Masking the features to the board matters as much as
   the registration does — board and wall sit at different depths, so once the
   camera translates no single homography fits both, and an unmasked fit
   happily locks onto the wall and leaves the board misaligned.
2. Difference the two, threshold, and clean up. Whatever is left is what the
   throw added, which is a far stronger signal than the dart's own appearance:
   a dart is dark, thin and lands on a board that is mostly dark and thin.
3. Take the largest surviving blob as the dart and fit its principal axis.
4. Pick the end nearer the board centre as the tip. Shaft and flight stick out
   of the board plane and therefore project *away* from the centre, so the
   inner end is the one actually touching the board — and it is the only part
   of the dart the homography is valid for.
5. Map the tip through the homography and read off the segment.

Because differencing is against the previous frame rather than an empty board,
darts already in the board cancel out. Occlusion only matters when a new dart
hides an old one, not merely when three of them sit side by side.
"""

import math

import cv2
import numpy as np

from app.api.features.calibration.entity.board_geometry import (
    DOUBLE_OUTER_RADIUS,
    segment_at,
)
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.detection.entity.dart import Dart
from app.api.features.detection.entity.detection_failure import DetectionFailure
from app.api.features.detection.entity.detection_trace import DetectionTrace

# How far out from the bull to look. Beyond the scoring area on purpose: a dart
# in the surround has to be found to be reported as a miss, otherwise it is
# indistinguishable from no throw at all.
_DETECTION_RADIUS_MM = 225.0

# ORB features for registration, and how many must survive RANSAC. The test set
# yields 340-1200 inliers on the board alone, so this is a wide margin.
_ORB_FEATURES = 4000
_MIN_ALIGNMENT_INLIERS = 40
_RANSAC_REPROJECTION_PX = 2.0

# Per-pixel difference counting as changed, in grey levels. Sensor noise sits
# around 2-4, so this is far above it while still catching a dark dart against
# a black segment.
_DIFFERENCE_THRESHOLD = 40

# Structuring elements and area limits in millimetres, converted to pixels per
# frame from the homography. The board's size in the image depends on where the
# phone is; expressing these as lengths on the board keeps one set of numbers
# valid at any distance.
_CLOSE_KERNEL_MM = 3.0
_MIN_DART_AREA_MM2 = 20.0

# Speckle is removed by area rather than by a morphological opening. An opening
# cannot help here: OpenCV's smallest usable structuring element is 3x3, which
# at the scale a phone actually frames a board (0.6-0.9 px/mm on the test set)
# is 3-5 mm across — wider than the dart it is meant to preserve. Measured, it
# threw away 60 % of the dart's own pixels. Dropping components below a plain
# area limit removes the same noise without eroding anything.
_MIN_SPECKLE_AREA_MM2 = 3.0

# How much of the axis end to average into the tip position. A single extreme
# pixel is whatever the threshold happened to catch; a few millimetres of it is
# stable.
_TIP_SPAN_MM = 3.0

# What the most recent call to `detect_dart` saw at each stage.
trace = DetectionTrace()


def detect_dart(
    reference: np.ndarray, frame: np.ndarray, calibration: Calibration
) -> Dart | DetectionFailure:
    """Find the dart added in `frame` relative to `reference`.

    `calibration` must be the calibration of `reference`; the incoming frame is
    warped onto it rather than calibrated in its own right. Two independent
    ellipse fits do not agree closely enough for differencing — on the test set
    the fitted axes drifted by 7 % between consecutive frames of one series,
    which is enough to light up every wire on the board.
    """
    global trace
    trace = DetectionTrace(reference=reference, frame=frame)

    pixels_per_mm = _pixels_per_mm(calibration.homography)
    trace.pixels_per_mm = pixels_per_mm

    region = _board_region(calibration.homography, reference.shape, _DETECTION_RADIUS_MM)

    alignment, inliers = _align(frame, reference, region)
    trace.alignment, trace.alignment_inliers = alignment, inliers
    if alignment is None:
        return _record_failure(DetectionFailure.ALIGNMENT_FAILED)

    aligned = cv2.warpPerspective(frame, alignment, reference.shape[1::-1])
    trace.aligned = aligned

    mask = _change_mask(reference, aligned, region, pixels_per_mm)
    trace.change_mask = mask

    blob = _largest_blob(mask, pixels_per_mm)
    if blob is None:
        return _record_failure(DetectionFailure.NO_CHANGE)

    tip, far_end = _tip_and_far_end(blob, calibration.homography, pixels_per_mm)
    board_point = _to_board(calibration.homography, tip)

    return Dart(
        tip_image=tip,
        axis_image=(tip, far_end),
        tip_board=board_point,
        segment=segment_at(*board_point),
    )


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
    """Image scale at the board, averaged around the double ring.

    Perspective makes this vary across the board, so it is only ever used to
    size kernels and area limits — never to convert a measurement.
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


def _board_region(homography: np.ndarray, shape: tuple[int, ...], radius_mm: float) -> np.ndarray:
    """A filled mask of the board out to `radius_mm`, in image space."""
    points = np.array(
        [
            _to_image(homography, radius_mm * math.cos(angle), radius_mm * math.sin(angle))
            for angle in np.linspace(0, 2 * math.pi, 180, endpoint=False)
        ],
        dtype=np.int32,
    )
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    return mask


def _align(
    frame: np.ndarray, reference: np.ndarray, region: np.ndarray
) -> tuple[np.ndarray | None, int]:
    """Homography warping `frame` onto `reference`, from board features alone.

    The darts already in the board are outliers here — they are genuinely in
    different places in the two frames — but they are a handful of features
    against several hundred on the board itself, so RANSAC discards them.
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


def _change_mask(
    reference: np.ndarray, aligned: np.ndarray, region: np.ndarray, pixels_per_mm: float
) -> np.ndarray:
    """Binary mask of what the throw added, inside the board region.

    Differenced per channel and maxed rather than converted to grey first: a
    dart barrel against a black segment can be nearly identical in luminance
    while still differing in colour, and collapsing to grey throws that away.
    """
    difference = cv2.absdiff(reference, aligned).max(axis=2)
    trace.difference = difference

    _, mask = cv2.threshold(difference, _DIFFERENCE_THRESHOLD, 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_and(mask, region)

    # Speckle first, then bridging. The order matters: closing first would join
    # scattered noise into blobs big enough to pass the area limit, and a dart
    # is dark on a dark board, so its own silhouette arrives in pieces that only
    # the closing puts back together.
    mask = _drop_speckle(mask, pixels_per_mm)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _kernel(_CLOSE_KERNEL_MM, pixels_per_mm))


def _drop_speckle(mask: np.ndarray, pixels_per_mm: float) -> np.ndarray:
    """Remove components too small to be part of a dart."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    minimum_area = _MIN_SPECKLE_AREA_MM2 * pixels_per_mm**2
    kept = [
        label for label in range(1, count) if stats[label, cv2.CC_STAT_AREA] >= minimum_area
    ]
    if not kept:
        return np.zeros_like(mask)
    return np.isin(labels, kept).astype(np.uint8) * 255


def _kernel(size_mm: float, pixels_per_mm: float) -> np.ndarray:
    """An elliptical structuring element of a given size on the board."""
    size = max(3, int(round(size_mm * pixels_per_mm)) | 1)  # odd, at least 3
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _largest_blob(mask: np.ndarray, pixels_per_mm: float) -> np.ndarray | None:
    """Pixel coordinates of the biggest change, or None if nothing is big enough."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    minimum_area = _MIN_DART_AREA_MM2 * pixels_per_mm**2

    candidates = [
        label for label in range(1, count) if stats[label, cv2.CC_STAT_AREA] >= minimum_area
    ]
    if not candidates:
        return None

    chosen = max(candidates, key=lambda label: stats[label, cv2.CC_STAT_AREA])
    trace.labels, trace.chosen_label = labels, chosen

    rows, columns = np.where(labels == chosen)
    return np.column_stack((columns, rows)).astype(np.float64)


def _tip_and_far_end(
    points: np.ndarray, homography: np.ndarray, pixels_per_mm: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The dart's two ends along its principal axis, tip first.

    The tip is the end nearer the board centre. Everything above the board
    surface — barrel, shaft, flight — is imaged further out than the point it
    actually sticks in, because the camera looks at the board from the front;
    the inner end is therefore the one in the board plane.
    """
    mean, eigenvectors = cv2.PCACompute(points, mean=None, maxComponents=1)
    axis = eigenvectors[0]
    projections = (points - mean) @ axis

    centre = np.array(_to_image(homography, 0.0, 0.0))
    ends = []
    for extreme in (projections.min(), projections.max()):
        # Average a few millimetres in from the end rather than trusting the one
        # pixel that happened to be furthest out.
        span = np.abs(projections - extreme) <= _TIP_SPAN_MM * pixels_per_mm
        ends.append(points[span].mean(axis=0))

    ends.sort(key=lambda end: float(np.hypot(*(end - centre))))
    return tuple(ends[0]), tuple(ends[1])
