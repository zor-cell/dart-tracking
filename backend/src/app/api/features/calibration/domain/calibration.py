"""Result of a board calibration."""

from dataclasses import dataclass

import numpy as np

from app.api.features.calibration.domain.board_geometry import STANDARD_RINGS, RingRadii


@dataclass
class Calibration:
    """Maps image pixels to the canonical board plane and back.

    `homography` takes image pixel coordinates to board millimetres (origin at
    the bullseye); `inverse` goes the other way and is what the overlay uses to
    draw the board model onto the camera picture.
    """

    homography: np.ndarray  # 3x3, image -> board
    image_width: int
    image_height: int
    rings: RingRadii = STANDARD_RINGS  # as measured on this board's picture

    @property
    def inverse(self) -> np.ndarray:
        """Board millimetres -> image pixels."""
        return np.linalg.inv(self.homography)
