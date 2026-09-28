"""Render every stage of a `detect_board` run as separate images.

Turns a `CalibrationTrace` into pictures, one per stage, so a bad fit can be
traced back to the stage that actually caused it instead of just the final
overlay being off. Used both by scripts/calibration/run_debug.py (a photo on disk) and,
when a calibration attempt asks for it, by the calibration websocket endpoint
(a frame sent live over the socket) — the trace looks the same either way.
"""

from pathlib import Path

import cv2
import numpy as np

from app.api.features.calibration.domain.board_geometry import SECTOR_ORDER, sector_centre_angle
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.debug.trace import CalibrationTrace
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.services.board_overlay import build_overlay

# BGR throughout, chosen to read against a board's own red/green/black/white.
_COLOUR_HULL = (255, 255, 255)
_COLOUR_ELLIPSE = (255, 255, 255)
_COLOUR_PROJECTED = (0, 255, 255)  # yellow
_COLOUR_CENTRE = (255, 255, 255)  # white
_COLOUR_TRANSITION = (255, 255, 255)  # white
_COLOUR_WIRE_RED = (0, 0, 220)
_COLOUR_WIRE_GREEN = (0, 200, 0)
_COLOUR_OVERLAY = (255, 255, 255)
_COLOUR_KEPT_RED = (0, 0, 255)
_COLOUR_KEPT_GREEN = (0, 255, 0)
_COLOUR_DROPPED_OFF_BOARD = (70, 70, 70)  # grey
_COLOUR_DROPPED_OUTER = (170, 120, 60)  # steel blue

_RING_DOT_RADIUS = 2
_MARKER_RADIUS = 5
# Board radius (mm) of the sector labels, in the outer single bed.
_LABEL_RADIUS = 135.0


def write_debug_images(
    trace: CalibrationTrace,
    outcome: Calibration | CalibrationFailure,
    out_dir: Path,
) -> list[Path]:
    """Write whichever stages the trace reached, and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    if trace.red_mask is not None:
        path = out_dir / "01_masks.jpg"
        cv2.imwrite(str(path), _draw_masks(trace))
        written.append(path)

    if trace.dropped_off_board is not None:
        path = out_dir / "02_components.jpg"
        cv2.imwrite(str(path), _draw_components(trace))
        written.append(path)

    if trace.hull is not None:
        path = out_dir / "03_hull_ellipse.jpg"
        cv2.imwrite(str(path), _draw_hull_ellipse(trace))
        written.append(path)

    for index in range(len(trace.passes)):
        path = out_dir / f"04_pass{index + 1}_wires.jpg"
        cv2.imwrite(str(path), _draw_pass(trace, index))
        written.append(path)

        if trace.passes[index].correspondences is not None:
            path = out_dir / f"05_pass{index + 1}_correspondences.jpg"
            cv2.imwrite(str(path), _draw_correspondences(trace, index))
            written.append(path)

    if not isinstance(outcome, CalibrationFailure):
        path = out_dir / "06_result.jpg"
        cv2.imwrite(str(path), _draw_result(trace, outcome))
        written.append(path)

    return written


def _draw_masks(trace: CalibrationTrace) -> np.ndarray:
    """Where red/green were classified — the raw material everything else builds on."""
    canvas = np.zeros_like(trace.image)
    canvas[..., 2] = trace.red_mask
    canvas[..., 1] = trace.green_mask
    return canvas


def _draw_components(trace: CalibrationTrace) -> np.ndarray:
    """Which mask components reached the ellipse fit, and what cut the others.

    Red and green are what survived; those pixels alone decide the fit. Grey
    did not vote for the winning board hypothesis — it lies at no plausible
    ring radius, so it is clutter, branding, or lettering. Steel blue did vote
    but was then trimmed for sitting outside the double ring. Comparing this
    against 01_masks.jpg says whether a skewed ellipse came from bad
    segmentation or from bad filtering.
    """
    canvas = np.zeros_like(trace.image)

    # Drawn first so the survivors paint over anything they overlap.
    if trace.dropped_off_board is not None:
        canvas[trace.dropped_off_board > 0] = _COLOUR_DROPPED_OFF_BOARD
    if trace.dropped_outer is not None:
        canvas[trace.dropped_outer > 0] = _COLOUR_DROPPED_OUTER
    if trace.kept_red is not None:
        canvas[trace.kept_red > 0] = _COLOUR_KEPT_RED
    if trace.kept_green is not None:
        canvas[trace.kept_green > 0] = _COLOUR_KEPT_GREEN

    return canvas


def _draw_hull_ellipse(trace: CalibrationTrace) -> np.ndarray:
    """The convex hull feeding fitEllipse, and what came out of it.

    A hull bulging out towards clutter outside the board (backboard text,
    stray coloured pixels) is the most common way the ellipse — and therefore
    everything downstream — comes out skewed.
    """
    canvas = trace.image.copy()
    if trace.hull is not None:
        cv2.polylines(canvas, [trace.hull.astype(np.int32)], True, _COLOUR_HULL, 2, cv2.LINE_AA)
    if trace.ellipse is not None:
        cv2.ellipse(canvas, trace.ellipse, _COLOUR_ELLIPSE, 2, cv2.LINE_AA)
        centre = tuple(round(c) for c in trace.ellipse[0])
        cv2.drawMarker(canvas, centre, _COLOUR_ELLIPSE, cv2.MARKER_CROSS, 20, 3)
    return canvas


def _draw_pass(trace: CalibrationTrace, index: int, label_projection: bool = True) -> np.ndarray:
    """One refinement pass: rays from the centre estimate, coloured by vote.

    The dot colour is what the ring walk decided at that angle (red/green/grey
    for "unclear"); the blue ticks are where a colour transition was placed.
    Comparing this against the real photo shows whether the wires the pipeline
    thinks it found actually sit on the true sector boundaries.
    """
    current = trace.passes[index]
    canvas = trace.image.copy()
    ellipse = trace.ellipse

    for step, colour in enumerate(current.ring_colours):
        parameter = 2 * 3.141592653589793 * step / len(current.ring_colours)
        x, y = board_detector._ellipse_point(ellipse, parameter)
        dot_colour = (
            _COLOUR_WIRE_RED
            if colour == 1
            else _COLOUR_WIRE_GREEN
            if colour == -1
            else (90, 90, 90)
        )
        cv2.circle(canvas, (round(x), round(y)), _RING_DOT_RADIUS, dot_colour, -1)

    for parameter, _ in current.transitions:
        x, y = board_detector._ellipse_point(ellipse, parameter)
        cv2.circle(canvas, (round(x), round(y)), _MARKER_RADIUS, _COLOUR_TRANSITION, 2)

    centre_point = (round(current.centre[0]), round(current.centre[1]))
    cv2.drawMarker(canvas, centre_point, _COLOUR_CENTRE, cv2.MARKER_TILTED_CROSS, 14, 2)

    if current.projected_centre is not None:
        refined_point = (round(current.projected_centre[0]), round(current.projected_centre[1]))
        cv2.drawMarker(canvas, refined_point, _COLOUR_PROJECTED, cv2.MARKER_CROSS, 14, 2)

    if current.projected_centre is not None and label_projection:
        text_position = (refined_point[0] + 5, refined_point[1] - 5)
        cv2.putText(
            img=canvas,
            text="proj",
            org=text_position,
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=0.4,
            color=_COLOUR_PROJECTED,
            thickness=1,
            lineType=cv2.LINE_AA
        )

    return canvas


def _draw_correspondences(trace: CalibrationTrace, index: int, draw_labels: bool = True) -> np.ndarray:
    """The matched wires as rays from the centre, and each sector's number under this pass's homography."""
    current = trace.passes[index]
    canvas = trace.image.copy()
    if current.correspondences is None:
        return canvas

    centre = (round(current.centre[0]), round(current.centre[1]))
    wires = [board_detector._ellipse_point(trace.ellipse, parameter) for parameter, _ in current.correspondences]
    for x, y in wires:
        cv2.line(canvas, centre, (round(x), round(y)), _COLOUR_OVERLAY, 1, cv2.LINE_AA)
    for x, y in wires:
        cv2.circle(canvas, (round(x), round(y)), _MARKER_RADIUS, _COLOUR_ELLIPSE, -1)

    if draw_labels:
        for text, position in sector_label_positions(trace, index):
            _put_centred_label(canvas, text, position)
    return canvas


def sector_label_positions(trace: CalibrationTrace, index: int) -> list[tuple[str, tuple[float, float]]]:
    """Each sector's number and its image position under this pass's homography."""
    homography = trace.passes[index].homography
    if homography is None:
        return []

    board_to_image = np.linalg.inv(homography)
    labels = []
    for sector, value in enumerate(SECTOR_ORDER):
        angle = sector_centre_angle(sector)
        board_point = np.array([[[_LABEL_RADIUS * np.cos(angle), _LABEL_RADIUS * np.sin(angle)]]])
        x, y = cv2.perspectiveTransform(board_point, board_to_image)[0, 0]
        labels.append((str(value), (float(x), float(y))))
    return labels


def _put_centred_label(canvas: np.ndarray, text: str, centre: tuple[float, float]) -> None:
    """White text with a black outline, centred on `centre`."""
    font, scale = cv2.FONT_HERSHEY_SIMPLEX, 0.7
    (width, height), _ = cv2.getTextSize(text, font, scale, 2)
    origin = (round(centre[0] - width / 2), round(centre[1] + height / 2))
    cv2.putText(canvas, text, origin, font, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(canvas, text, origin, font, scale, (255, 255, 255), 2, cv2.LINE_AA)


def _draw_result(trace: CalibrationTrace, calibration: Calibration) -> np.ndarray:
    """The final board model projected back onto the photo."""
    canvas = trace.image.copy()
    height, width = canvas.shape[:2]
    for line in build_overlay(calibration):
        points = np.array([[p[0] * width, p[1] * height] for p in line], dtype=np.int32)
        cv2.polylines(canvas, [points], False, _COLOUR_OVERLAY, 1, cv2.LINE_AA)
    return canvas
