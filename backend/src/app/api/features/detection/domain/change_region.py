"""Where the client's trigger saw the picture change since just before the throw."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChangeRegion:
    """A box of the trigger's grid cells, over the whole camera frame."""

    col: int
    row: int
    cols: int
    rows: int
    grid_cols: int
    grid_rows: int

    def corners(self, width: int, height: int) -> np.ndarray:
        """The box's corners in pixels of a `width` x `height` frame, as a (4, 1, 2) array."""
        left, right = self.col / self.grid_cols * width, (self.col + self.cols) / self.grid_cols * width
        top, bottom = self.row / self.grid_rows * height, (self.row + self.rows) / self.grid_rows * height
        return np.float32([[left, top], [right, top], [right, bottom], [left, bottom]]).reshape(-1, 1, 2)
