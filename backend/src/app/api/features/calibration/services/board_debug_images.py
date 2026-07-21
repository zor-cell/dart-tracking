"""Render every stage of a `detect_board` run as separate images.

Turns a `CalibrationTrace` into pictures, one per stage, so a bad fit can be
traced back to the stage that actually caused it instead of just the final
overlay being off. Used both by scripts/debug_images.py (a photo on disk) and,
when a calibration attempt asks for it, by the calibration websocket endpoint
(a frame sent live over the socket) — the trace looks the same either way.
"""

from pathlib import Path

import cv2
import numpy as np

from app.api.features.calibration.entity.board_geometry import SECTOR_COUNT, is_red_sector
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure
from app.api.features.calibration.entity.calibration_trace import CalibrationTrace
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.services.board_overlay import build_overlay

# BGR throughout, chosen to read against a board's own red/green/black/white.
_COLOUR_HULL = (255, 0, 255)  # magenta
_COLOUR_ELLIPSE = (0, 255, 255)  # yellow
_COLOUR_CENTRE = (255, 255, 255)  # white
_COLOUR_TRANSITION = (255, 128, 0)  # blue
_COLOUR_WIRE_RED = (0, 0, 220)
_COLOUR_WIRE_GREEN = (0, 200, 0)
_COLOUR_OVERLAY = (0, 255, 255)

_RING_DOT_RADIUS = 2
_MARKER_RADIUS = 5


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

    if trace.hull is not None:
        path = out_dir / "02_hull_ellipse.jpg"
        cv2.imwrite(str(path), _draw_hull_ellipse(trace))
        written.append(path)

    for index in range(len(trace.passes)):
        path = out_dir / f"03_pass{index + 1}_wires.jpg"
        cv2.imwrite(str(path), _draw_pass(trace, index))
        written.append(path)

        if trace.passes[index].correspondences is not None:
            path = out_dir / f"04_pass{index + 1}_correspondences.jpg"
            cv2.imwrite(str(path), _draw_correspondences(trace, index))
            written.append(path)

    if not isinstance(outcome, CalibrationFailure):
        path = out_dir / "05_result.jpg"
        cv2.imwrite(str(path), _draw_result(trace, outcome))
        written.append(path)

    return written


def _draw_masks(trace: CalibrationTrace) -> np.ndarray:
    """Where red/green were classified — the raw material everything else builds on."""
    canvas = np.zeros_like(trace.image)
    canvas[..., 2] = trace.red_mask
    canvas[..., 1] = trace.green_mask
    return canvas


def _draw_hull_ellipse(trace: CalibrationTrace) -> np.ndarray:
    """The convex hull feeding fitEllipse, and what came out of it.

    A hull bulging out towards clutter outside the board (backboard text,
    stray coloured pixels) is the most common way the ellipse — and therefore
    everything downstream — comes out skewed.
    """
    canvas = trace.image.copy()
    if trace.hull is not None:
        cv2.polylines(canvas, [trace.hull.astype(np.int32)], True, _COLOUR_HULL, 1, cv2.LINE_AA)
    if trace.ellipse is not None:
        cv2.ellipse(canvas, trace.ellipse, _COLOUR_ELLIPSE, 1, cv2.LINE_AA)
        centre = tuple(round(c) for c in trace.ellipse[0])
        cv2.drawMarker(canvas, centre, _COLOUR_ELLIPSE, cv2.MARKER_CROSS, 12, 1)
    return canvas


def _draw_pass(trace: CalibrationTrace, index: int) -> np.ndarray:
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
    cv2.drawMarker(canvas, centre_point, _COLOUR_CENTRE, cv2.MARKER_CROSS, 14, 2)

    if current.projected_centre is not None:
        refined_point = (round(current.projected_centre[0]), round(current.projected_centre[1]))
        cv2.drawMarker(canvas, refined_point, _COLOUR_ELLIPSE, cv2.MARKER_DIAMOND, 14, 2)

    return canvas


def _draw_correspondences(trace: CalibrationTrace, index: int) -> np.ndarray:
    """Which wire each transition was assigned to, once a pass has a match.

    Sector 0 (the 20) is marked distinctly so a rotation that is one or two
    sectors off — colour alternation alone leaves that ambiguous — is visible
    at a glance rather than only showing up as a wrong score later.
    """
    current = trace.passes[index]
    canvas = trace.image.copy()
    if current.correspondences is None:
        return canvas

    for wire, (parameter, board_angle) in enumerate(current.correspondences):
        x, y = board_detector._ellipse_point(trace.ellipse, parameter)
        colour = _COLOUR_WIRE_RED if is_red_sector(wire % SECTOR_COUNT) else _COLOUR_WIRE_GREEN
        cv2.circle(canvas, (round(x), round(y)), _MARKER_RADIUS, colour, -1)
        cv2.putText(
            canvas,
            str(wire),
            (round(x) + 6, round(y)),
            cv2.FONT_HERSHEY_PLAIN,
            1.0,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def _draw_result(trace: CalibrationTrace, calibration: Calibration) -> np.ndarray:
    """The final board model projected back onto the photo."""
    canvas = trace.image.copy()
    height, width = canvas.shape[:2]
    for line in build_overlay(calibration):
        points = np.array([[p[0] * width, p[1] * height] for p in line], dtype=np.int32)
        cv2.polylines(canvas, [points], False, _COLOUR_OVERLAY, 1, cv2.LINE_AA)
    return canvas
