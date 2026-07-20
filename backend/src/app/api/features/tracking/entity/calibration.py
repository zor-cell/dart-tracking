"""Result of a board calibration."""

from dataclasses import dataclass

import numpy as np


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

    @property
    def inverse(self) -> np.ndarray:
        """Board millimetres -> image pixels."""
        return np.linalg.inv(self.homography)

    def to_list(self) -> list[list[float]]:
        """Row-major form for the wire."""
        return self.homography.tolist()
