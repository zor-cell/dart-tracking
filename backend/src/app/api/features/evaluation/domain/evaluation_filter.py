"""Which logged games the evaluation page reads. Every field narrows them to any of its
values; an empty or None one leaves them open."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.evaluation.domain.accuracy import LoggedGame
from app.api.features.game.domain.game_mode import GameMode


@dataclass(frozen=True)
class EvaluationFilter:
    # Tracker versions every one of the game's events has to come from.
    versions: tuple[int, ...] = ()
    modes: tuple[GameMode, ...] = ()
    # True for test runs only, False for ordinary games only.
    test_run: bool | None = None
    # Bounds on the start of the game; `until` is exclusive.
    since: datetime | None = None
    until: datetime | None = None

    def selects(self, game: LoggedGame) -> bool:
        if self.versions and not (
            game.tracker_versions and set(game.tracker_versions) <= set(self.versions)
        ):
            return False
        if self.modes and game.mode not in self.modes:
            return False
        if self.test_run is not None and game.evaluation_enabled is not self.test_run:
            return False
        if self.since is not None and game.created_at < self.since:
            return False
        return self.until is None or game.created_at < self.until
