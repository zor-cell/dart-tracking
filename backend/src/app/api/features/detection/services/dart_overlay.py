"""Draws the located dart back onto the camera picture.

The counterpart to `calibration/services/board_overlay.py`: it lets the user see
what the server actually found — the dart's axis and, marked apart, the scored
tip. If the line lies along the real dart and the cross sits on the tip, the
detection is good.

Unlike the board overlay, no projection is needed: a `Dart` already carries its
axis and tip in **reference-frame pixels** (detection aligns the incoming frame
onto the reference before measuring), so this only normalizes them to 0..1 of the
image size — the same wire contract the board overlay uses, so the client draws
both the same way.
"""

from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.detection.entity.detection import Dart

# Half-length of each tip crosshair arm, in pixels. Small: it marks the scored
# point without smothering it.
_TIP_MARKER_PX = 6.0


def build_overlay(dart: Dart, calibration: Calibration) -> list[list[list[float]]]:
    """The dart's axis and a tip crosshair as normalized polylines."""
    (tip_x, tip_y) = dart.tip_image
    return [
        # The principal axis, tip end first.
        _normalize([dart.axis_image[0], dart.axis_image[1]], calibration),
        # Crosshair on the tip: one horizontal arm, one vertical.
        _normalize(
            [(tip_x - _TIP_MARKER_PX, tip_y), (tip_x + _TIP_MARKER_PX, tip_y)],
            calibration,
        ),
        _normalize(
            [(tip_x, tip_y - _TIP_MARKER_PX), (tip_x, tip_y + _TIP_MARKER_PX)],
            calibration,
        ),
    ]


def _normalize(
    points: list[tuple[float, float]], calibration: Calibration
) -> list[list[float]]:
    """Image pixels -> normalized 0..1 image coordinates."""
    return [
        [x / calibration.image_width, y / calibration.image_height] for x, y in points
    ]
