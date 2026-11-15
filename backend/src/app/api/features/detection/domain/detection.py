"""A located dart: where it is, and what it scored."""

from dataclasses import dataclass

from app.api.features.calibration.domain.board_geometry import Segment


@dataclass(frozen=True)
class Dart:
    """Where the dart was found and what it is worth; image coordinates are in the
    reference frame's pixel grid.
    """

    tip_image: tuple[float, float]
    # Both ends of the dart's principal axis, tip first; the flight end is for
    # drawing only.
    axis_image: tuple[tuple[float, float], tuple[float, float]]
    tip_board: tuple[float, float]  # millimetres
    segment: Segment

    @property
    def points(self) -> int:
        return self.segment.points
