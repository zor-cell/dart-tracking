"""In-memory calibration store, keyed by game.

Kept alongside the game rather than on the WebSocket connection: a calibration
outlives any single socket (a reconnecting client must not have to re-aim the
camera), and it is per board setup, which is what a game is.

Same caveats as the game store — process-local, lost on restart.
"""

from app.api.features.tracking.entity.calibration import Calibration


class CalibrationStore:
    def __init__(self) -> None:
        self._calibrations: dict[str, Calibration] = {}

    def set(self, game_id: str, calibration: Calibration) -> None:
        """Store a calibration, replacing any earlier one for that game."""
        self._calibrations[game_id] = calibration

    def get(self, game_id: str) -> Calibration | None:
        return self._calibrations.get(game_id)


# Module-level singleton store.
store = CalibrationStore()
