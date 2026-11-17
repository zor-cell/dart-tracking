"""What the visits of a training without a target add up to: points, as in x01."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.turn import Turn
from app.api.features.statistics.domain.player_statistics import VisitRef


@dataclass
class ScoringGame:
    game_id: str
    played_at: datetime
    darts: int = 0
    points: int = 0

    @property
    def average(self) -> float:
        """Points per three darts."""
        return 0.0 if self.darts == 0 else 3 * self.points / self.darts


@dataclass
class ScoringStatistics:
    darts: int = 0
    points: int = 0
    best_visit: int = 0
    best_visit_at: VisitRef | None = None
    visit_scores: Counter[int] = field(default_factory=Counter)  # visits by points
    # One per game with darts, oldest first.
    games: list[ScoringGame] = field(default_factory=list)

    @property
    def average(self) -> float:
        return 0.0 if self.darts == 0 else 3 * self.points / self.darts

    def visits_from(self, points: int) -> int:
        """Visits that scored at least `points`."""
        return sum(count for score, count in self.visit_scores.items() if score >= points)

    def add_game(
        self,
        game_id: str,
        played_at: datetime,
        turns: Sequence[Turn],
        refs: Sequence[VisitRef | None],
    ) -> None:
        """Counts one game's own visits; games come oldest first, so a tie keeps the oldest."""
        game = ScoringGame(game_id, played_at)
        for turn, ref in zip(turns, refs, strict=True):
            if not turn.darts:
                continue
            game.darts += len(turn.darts)
            game.points += turn.points
            self.visit_scores[turn.points] += 1
            if turn.points > self.best_visit:
                self.best_visit, self.best_visit_at = turn.points, ref
        if game.darts == 0:
            return
        self.darts += game.darts
        self.points += game.points
        self.games.append(game)
