"""Cricket figures: marks per round, how near the darts came to a number still open, the
marks of each visit, and where the darts landed."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.cricket import CricketOptions, cricket_throws
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.target import Target
from app.api.features.statistics.domain.heatmap import HitPattern
from app.api.features.statistics.domain.player_statistics import VisitRef

def marks_per_round(marks: int, darts: int) -> float | None:
    return None if darts == 0 else 3 * marks / darts


@dataclass
class CricketGame:
    game_id: str
    played_at: datetime
    won: bool
    darts: int = 0
    marks: int = 0
    located: int = 0
    # Summed mm of the located darts from the nearest number still open, 0 on one.
    distance: float = 0.0

    @property
    def mpr(self) -> float | None:
        return marks_per_round(self.marks, self.darts)

    @property
    def mean_distance(self) -> float | None:
        return None if self.located == 0 else self.distance / self.located


@dataclass
class CricketStatistics:
    # Oldest first.
    games: list[CricketGame] = field(default_factory=list)
    games_with_opponent: int = 0
    wins: int = 0
    # Darts that marked nothing.
    empty: int = 0
    # Visits by the marks they counted.
    visits: Counter[int] = field(default_factory=Counter)
    best_visit: int = 0
    best_visit_at: VisitRef | None = None
    hits: HitPattern = field(default_factory=HitPattern)

    def add_game(self, game: Game, seat: int, played_at: datetime) -> None:
        assert isinstance(game.options, CricketOptions)
        winner = game.winner
        tally = CricketGame(game.id, played_at, won=winner is not None and winner.id == seat)
        visit_of = _visit_numbers(game)
        marks_of: dict[int, int] = {}
        ids = [player.id for player in game.players]
        for throw in cricket_throws(ids, game.turns, game.options):
            if throw.player_id != seat:
                continue
            dart = throw.dart
            tally.darts += 1
            tally.marks += throw.marks
            marks_of[throw.turn] = marks_of.get(throw.turn, 0) + throw.marks
            self.empty += throw.marks == 0
            self.hits.add(dart)
            if dart.position is None:
                continue
            if throw.open:
                tally.located += 1
                tally.distance += min(
                    Target(value, None).distance(*dart.position) for value in throw.open
                )
        for turn, marks in marks_of.items():
            self.visits[marks] += 1
            if marks > self.best_visit:
                self.best_visit = marks
                self.best_visit_at = VisitRef(game.id, visit_of[turn], played_at)
        if len(game.players) > 1:
            self.games_with_opponent += 1
            self.wins += tally.won
        self.games.append(tally)

    @property
    def darts(self) -> int:
        return sum(game.darts for game in self.games)

    @property
    def marks(self) -> int:
        return sum(game.marks for game in self.games)

    @property
    def mpr(self) -> float | None:
        return marks_per_round(self.marks, self.darts)

    @property
    def mean_distance(self) -> float | None:
        located = sum(game.located for game in self.games)
        return None if located == 0 else sum(game.distance for game in self.games) / located

    @property
    def favourite_visit(self) -> int | None:
        """The marks a visit counted most often, the higher on a tie."""
        if not self.visits:
            return None
        return max(self.visits, key=lambda marks: (self.visits[marks], marks))


def _visit_numbers(game: Game) -> dict[int, int]:
    """Each turn with darts by its place among the game's visits, as the replay counts them."""
    with_darts = [index for index, turn in enumerate(game.turns) if turn.darts]
    return {turn: visit for visit, turn in enumerate(with_darts)}
