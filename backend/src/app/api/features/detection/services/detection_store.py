"""In-memory reference-frame store, keyed by game.

Detection differences each throw against the *previous* frame rather than
against an empty board (see `dart_detector`), so it needs the last frame it saw
kept around per game. This holds it.

The stored frame lives in the reference frame's pixel grid — the one the
game's calibration homography belongs to. It is seeded with the calibration
frame (the empty board) the moment calibration succeeds, and rolled forward to
the aligned copy of each throw as it is scored, so consecutive throws stay in
that same grid.

Same caveats as the calibration and game stores: process-local, lost on
restart, not shared across workers.
"""

import numpy as np


class DetectionStore:
    def __init__(self) -> None:
        self._frames: dict[str, np.ndarray] = {}

    def set(self, game_id: str, frame: np.ndarray) -> None:
        """Store the frame the next throw should be differenced against."""
        self._frames[game_id] = frame

    def get(self, game_id: str) -> np.ndarray | None:
        return self._frames.get(game_id)


store = DetectionStore()
