"""In-memory reference-frame store, keyed by game and camera.

Detection differences each throw against the *previous* frame rather than
against an empty board (see `dart_detector`), so it needs the last frame it saw
kept around. This holds it.

The stored frame lives in the reference frame's pixel grid — the one that
camera's calibration homography belongs to. It is seeded with the calibration
frame (the empty board) the moment calibration succeeds, and rolled forward to
the aligned copy of each throw as it is scored, so consecutive throws stay in
that same grid. The calibration frame is also kept as it is, to tell a dart
pulled out of the board from one thrown into it.

That grid is what makes the client id part of the key: two cameras see the same
board through different homographies, so a frame from one is not a reference the
other could difference against. Every camera rolls its own forward, including
one whose detections are not the ones being booked (see `scoring_camera`).

Same caveats as the calibration and game stores: process-local, lost on
restart, not shared across workers.
"""

import numpy as np


class DetectionStore:
    def __init__(self) -> None:
        self._frames: dict[tuple[str, str], np.ndarray] = {}
        self._empty_boards: dict[tuple[str, str], np.ndarray] = {}

    def seed(self, game_id: str, client_id: str, empty_board: np.ndarray) -> None:
        """Start this camera over from a freshly calibrated, empty board."""
        self._frames[(game_id, client_id)] = empty_board
        self._empty_boards[(game_id, client_id)] = empty_board

    def set(self, game_id: str, client_id: str, frame: np.ndarray) -> None:
        """Store the frame this camera's next throw should be differenced against."""
        self._frames[(game_id, client_id)] = frame

    def get(self, game_id: str, client_id: str) -> np.ndarray | None:
        return self._frames.get((game_id, client_id))

    def empty_board(self, game_id: str, client_id: str) -> np.ndarray | None:
        return self._empty_boards.get((game_id, client_id))


store = DetectionStore()
