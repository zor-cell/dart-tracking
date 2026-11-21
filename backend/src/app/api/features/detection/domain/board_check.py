"""Whether a camera's calibration still fits the board, judged from a fresh frame
aligned onto the frame it was calibrated on.
"""

from dataclasses import dataclass, field

import numpy as np

# Matched board features the alignment must keep, how far the board may have
# moved (mm, averaged over its outline) and the share of it the frame must still see.
MIN_INLIERS = 500
MAX_SHIFT_MM = 20.0
MIN_COVERAGE = 0.99


@dataclass(frozen=True)
class BoardCheck:
    inliers: int
    shift_mm: float | None = None  # None when no alignment was found
    coverage: float = 0.0
    # The frame warped into the calibration frame's grid, if it aligned.
    aligned: np.ndarray | None = field(default=None, repr=False, compare=False)

    @property
    def holds(self) -> bool:
        return (
            self.aligned is not None
            and self.shift_mm is not None
            and self.inliers >= MIN_INLIERS
            and self.shift_mm <= MAX_SHIFT_MM
            and self.coverage >= MIN_COVERAGE
        )
