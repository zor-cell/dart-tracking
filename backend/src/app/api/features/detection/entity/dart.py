"""A located dart: where it is, and what it scored."""

from dataclasses import dataclass

from app.api.features.calibration.entity.board_geometry import Segment


@dataclass(frozen=True)
class Dart:
    """Where the dart was found and what it is worth.

    Image coordinates are in the **reference frame's** pixel grid, not the
    frame the dart arrived in: detection aligns the incoming frame onto the
    reference before comparing, so that is the grid everything downstream —
    overlay included — shares with the calibration.
    """

    tip_image: tuple[float, float]
    # Both ends of the dart's principal axis, tip end first. The far end is the
    # flight, which sticks out of the board plane and is therefore only
    # meaningful for drawing, never for scoring.
    axis_image: tuple[tuple[float, float], tuple[float, float]]
    tip_board: tuple[float, float]  # millimetres
    segment: Segment

    @property
    def points(self) -> int:
        return self.segment.points
