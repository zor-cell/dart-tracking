"""Everything a player threw, whatever the game: how much, where and when."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, tzinfo

from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.statistics.domain.activity import Activity, ActivityTally, activity
from app.api.features.statistics.domain.heatmap import HitPattern


@dataclass
class OverallStatistics:
    games: int = 0
    darts: int = 0
    # Summed time from setting a game up to its end, in seconds.
    seconds: float = 0.0
    games_with_opponent: int = 0
    wins: int = 0
    misses: int = 0
    located: int = 0
    # A miss counts under the label 0.
    hits: HitPattern = field(default_factory=HitPattern)
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: Counter[str] = field(default_factory=Counter)
    # Darts, games and time per day and variant.
    played: dict[tuple[date, GameVariant], ActivityTally] = field(default_factory=dict)
    # The zone the days are counted in.
    zone: tzinfo = UTC
    # The days the selection covers; None reaches to the first or the last game.
    first_day: date | None = None
    last_day: date | None = None

    def add_game(
        self, game: Game, seat: int, played_at: datetime, finished_at: datetime | None
    ) -> None:
        darts = [dart for turn in game.turns if turn.player_id == seat for dart in turn.darts]
        self.games += 1
        self.darts += len(darts)
        seconds = (
            0.0 if finished_at is None else max(0.0, (finished_at - played_at).total_seconds())
        )
        self.seconds += seconds
        day = played_at.astimezone(self.zone).date()
        tally = self.played.setdefault((day, game.variant), ActivityTally())
        tally.add(ActivityTally(len(darts), 1, seconds))
        for dart in darts:
            self.hits.add(dart)
            self.rings[_ring(dart.multiplier)] += 1
            self.misses += dart.multiplier == 0
            self.located += dart.position is not None
        if len(game.players) < 2:
            return
        self.games_with_opponent += 1
        winner = game.winner
        self.wins += winner is not None and winner.id == seat

    @property
    def activity(self) -> Activity | None:
        """What was played over the selected days and any game's day past them; None without
        a game."""
        if not self.played:
            return None
        days = [day for day, _ in self.played]
        first, last = min(days), max(days)
        return activity(
            self.played,
            min(first, self.first_day or first),
            max(last, self.last_day or last),
        )


def _ring(multiplier: int) -> str:
    if multiplier == 0:
        return "miss"
    return {1: "single", 2: "double", 3: "triple"}[multiplier]
