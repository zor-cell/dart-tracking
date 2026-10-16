"""Projects the canonical board model back onto the camera picture.

Lets the user confirm what the server actually recognised: if the rings sit on
the real rings and the sector wires line up, the calibration is good.

Coordinates come out normalized to 0..1 of the image width/height so the client
can draw them at whatever size the video is displayed at.
"""

import math

import numpy as np

from app.api.features.calibration.domain.board_geometry import (
    BULL_RADIUS,
    BULLSEYE_RADIUS,
    DOUBLE_OUTER_RADIUS,
    sector_boundary_angles,
)
from app.api.features.calibration.domain.calibration import Calibration

# Circles do not stay circles under perspective, so they are emitted as
# polylines dense enough to look smooth.
_CIRCLE_SEGMENTS = 72


def build_overlay(calibration: Calibration) -> list[list[list[float]]]:
    """Ring circles and sector wires as normalized polylines."""
    inverse = calibration.inverse
    rings = calibration.rings
    # Outermost last so it paints on top.
    radii = (
        BULLSEYE_RADIUS,
        BULL_RADIUS,
        rings.triple_inner,
        rings.triple_outer,
        rings.double_inner,
        rings.double_outer,
    )
    polylines = [_project(_circle_points(radius), inverse, calibration) for radius in radii]
    polylines.extend(
        _project(_sector_wire_points(angle), inverse, calibration)
        for angle in sector_boundary_angles()
    )
    return polylines


def _circle_points(radius: float) -> list[tuple[float, float]]:
    """Closed ring in board millimetres."""
    return [
        (
            radius * math.cos(2 * math.pi * step / _CIRCLE_SEGMENTS),
            radius * math.sin(2 * math.pi * step / _CIRCLE_SEGMENTS),
        )
        # +1 closes the loop back onto the first point.
        for step in range(_CIRCLE_SEGMENTS + 1)
    ]


def _sector_wire_points(angle: float) -> list[tuple[float, float]]:
    """One wire, running from the bull out to the edge of the scoring area.

    Straight lines stay straight under a homography, so two points are enough.
    """
    return [
        (BULL_RADIUS * math.cos(angle), BULL_RADIUS * math.sin(angle)),
        (DOUBLE_OUTER_RADIUS * math.cos(angle), DOUBLE_OUTER_RADIUS * math.sin(angle)),
    ]


def _project(
    board_points: list[tuple[float, float]],
    inverse: np.ndarray,
    calibration: Calibration,
) -> list[list[float]]:
    """Board millimetres -> normalized image coordinates."""
    homogeneous = np.array([[x, y, 1.0] for x, y in board_points]).T
    projected = inverse @ homogeneous

    # Guard the horizon: points whose w collapses to zero project to infinity.
    w = projected[2]
    w = np.where(np.abs(w) < 1e-9, 1e-9, w)

    xs = projected[0] / w / calibration.image_width
    ys = projected[1] / w / calibration.image_height

    return [[float(x), float(y)] for x, y in zip(xs, ys)]
