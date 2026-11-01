"""Which logged games the evaluation page reads. Every field narrows them; an empty or
None one leaves them open. All bounds are inclusive except `until`."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.evaluation.domain.accuracy import CameraAngle, LoggedGame
from app.api.features.game.domain.game_mode import GameMode


@dataclass(frozen=True)
class EvaluationFilter:
    # Tracker versions every one of the game's events has to lie between.
    version_from: int | None = None
    version_to: int | None = None
    modes: tuple[GameMode, ...] = ()
    # True for test runs only, False for ordinary games only.
    test_run: bool | None = None
    since: datetime | None = None
    until: datetime | None = None
    # The scoring camera's tilt to the board, in degrees.
    tilt_from: float | None = None
    tilt_to: float | None = None

    def selects(self, game: LoggedGame) -> bool:
        """Everything but the camera, which is only known once the log is read."""
        if self.version_from is not None or self.version_to is not None:
            versions = game.tracker_versions
            low, high = self.version_from, self.version_to
            if not versions or not _within(versions[0], versions[-1], low, high):
                return False
        if self.modes and game.mode not in self.modes:
            return False
        if self.test_run is not None and game.evaluation_enabled is not self.test_run:
            return False
        if self.since is not None and game.created_at < self.since:
            return False
        return self.until is None or game.created_at < self.until

    def selects_camera(self, camera: CameraAngle | None) -> bool:
        if self.tilt_from is None and self.tilt_to is None:
            return True
        if camera is None:
            return False
        return _within(camera.tilt, camera.tilt, self.tilt_from, self.tilt_to)


def _within(lowest: float, highest: float, low: float | None, high: float | None) -> bool:
    return (low is None or lowest >= low) and (high is None or highest <= high)
