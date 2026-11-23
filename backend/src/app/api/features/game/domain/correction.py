"""A dart corrected by hand keeps the camera's tip when it landed on the edge of the
field that was booked instead."""

from dataclasses import replace

from app.api.features.calibration.domain.board_geometry import (
    Segment,
    distance_to_segment,
    point_inside,
)
from app.api.features.game.domain.dart import Dart

# Farthest (mm) a located tip may lie outside the booked field and still be kept.
SNAP_MM = 2.0
# How far (mm) a kept tip is moved in from the field's edge.
SNAP_INSET_MM = 0.5


def keeps_tip(position: tuple[float, float], segment: Segment) -> bool:
    """Whether a tip at `position` is moved into `segment` when the dart is corrected to it."""
    return segment.multiplier != 0 and distance_to_segment(*position, segment) <= SNAP_MM


def corrected(tracked: Dart, entered: Dart) -> Dart:
    """`entered` in place of `tracked`, with the tracked tip moved just inside the
    entered field when it lay within `SNAP_MM` of it."""
    segment = Segment(entered.value, entered.multiplier)
    if tracked.position is None or tracked.snapped or not keeps_tip(tracked.position, segment):
        return entered
    position = point_inside(*tracked.position, segment, SNAP_INSET_MM)
    return replace(entered, position=position, snapped=True)
