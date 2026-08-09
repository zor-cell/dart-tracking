"""In-memory calibration store, keyed by game and camera.

Kept alongside the game rather than on the WebSocket connection: a calibration
outlives any single socket (a reconnecting client must not have to re-aim the
camera). It is per **camera in a position**, though, not per game — two phones
filming the same board from two angles have nothing in common to share, so the
client id is part of the key (see docs/feature/multi-device.md §5).

Same caveats as the game store — process-local, lost on restart.
"""

from app.api.features.calibration.domain.calibration import Calibration


class CalibrationStore:
    def __init__(self) -> None:
        self._calibrations: dict[tuple[str, str], Calibration] = {}

    def set(self, game_id: str, client_id: str, calibration: Calibration) -> None:
        """Store a calibration, replacing this camera's earlier one for the game."""
        self._calibrations[(game_id, client_id)] = calibration

    def get(self, game_id: str, client_id: str) -> Calibration | None:
        return self._calibrations.get((game_id, client_id))


store = CalibrationStore()
