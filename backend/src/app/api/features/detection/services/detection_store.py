"""In-memory reference frames keyed by game and camera: the last aligned frame each
throw is differenced against, the empty board, and the calibration frame both are
aligned to. Process-local, lost on restart.
"""

import numpy as np


class DetectionStore:
    def __init__(self) -> None:
        self._frames: dict[tuple[str, str], np.ndarray] = {}
        self._empty_boards: dict[tuple[str, str], np.ndarray] = {}
        self._anchors: dict[tuple[str, str], np.ndarray] = {}
        # Pixels of each dart located since the visit began, in the reference grid.
        self._darts: dict[tuple[str, str], list[np.ndarray]] = {}
        # The same for the visit that ended last, until the next one starts over.
        self._ended: dict[tuple[str, str], list[np.ndarray]] = {}

    def seed(self, game_id: str, client_id: str, empty_board: np.ndarray) -> None:
        """Start this camera over from a freshly calibrated, empty board."""
        self._anchors[(game_id, client_id)] = empty_board
        self.refresh(game_id, client_id, empty_board)

    def refresh(
        self, game_id: str, client_id: str, frame: np.ndarray, *, empty: bool = True
    ) -> None:
        """Start this camera over from `frame`, in its calibration frame's grid; it
        becomes the empty board too if `empty`."""
        self._frames[(game_id, client_id)] = frame
        if empty:
            self._empty_boards[(game_id, client_id)] = frame
        self._darts.pop((game_id, client_id), None)
        self._ended.pop((game_id, client_id), None)

    def set(self, game_id: str, client_id: str, frame: np.ndarray) -> None:
        """Store the frame this camera's next throw should be differenced against."""
        self._frames[(game_id, client_id)] = frame

    def get(self, game_id: str, client_id: str) -> np.ndarray | None:
        return self._frames.get((game_id, client_id))

    def empty_board(self, game_id: str, client_id: str) -> np.ndarray | None:
        return self._empty_boards.get((game_id, client_id))

    def anchor(self, game_id: str, client_id: str) -> np.ndarray | None:
        """The frame this camera's calibration was made on."""
        return self._anchors.get((game_id, client_id))

    def add_dart(self, game_id: str, client_id: str, pixels: np.ndarray) -> None:
        """Remember where a dart this camera located sits, until the visit ends."""
        self._darts.setdefault((game_id, client_id), []).append(pixels)

    def darts(self, game_id: str, client_id: str) -> list[np.ndarray]:
        return self._darts.get((game_id, client_id), [])

    def ended_darts(self, game_id: str, client_id: str) -> list[np.ndarray]:
        return self._ended.get((game_id, client_id), [])

    def end_visit(self, game_id: str) -> None:
        """Close the visit for every camera in the game: its located darts become the ended visit's."""
        for key in [key for key in self._ended if key[0] == game_id]:
            del self._ended[key]
        for key in [key for key in self._darts if key[0] == game_id]:
            self._ended[key] = self._darts.pop(key)


store = DetectionStore()
