"""Everything a player threw, whatever the game: how much, where and when."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.api.features.game.domain.game import Game
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
    variants: Counter[str] = field(default_factory=Counter)
    # A miss counts under the label 0.
    hits: HitPattern = field(default_factory=HitPattern)
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: Counter[str] = field(default_factory=Counter)
    # Darts per day the games were played on.
    days: Counter[date] = field(default_factory=Counter)

    def add_game(
        self, game: Game, seat: int, played_at: datetime, finished_at: datetime | None
    ) -> None:
        darts = [dart for turn in game.turns if turn.player_id == seat for dart in turn.darts]
        self.games += 1
        self.darts += len(darts)
        self.variants[game.variant.value] += 1
        if finished_at is not None:
            self.seconds += max(0.0, (finished_at - played_at).total_seconds())
        self.days[played_at.date()] += len(darts)
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
    def weeks(self) -> list[tuple[date, int]]:
        """Darts per week from the first played to the last, by its Monday, empty ones too."""
        if not self.days:
            return []
        totals: Counter[date] = Counter()
        for day, darts in self.days.items():
            totals[day - timedelta(days=day.weekday())] += darts
        week, last = min(totals), max(totals)
        weeks = []
        while week <= last:
            weeks.append((week, totals[week]))
            week += timedelta(weeks=1)
        return weeks

    @property
    def longest_streak(self) -> int:
        """The most days in a row with a game."""
        longest = run = 0
        previous: date | None = None
        for day in sorted(self.days):
            run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
            longest = max(longest, run)
            previous = day
        return longest

    @property
    def busiest_day(self) -> tuple[date, int] | None:
        """The day with the most darts, the earliest on a tie."""
        if not self.days:
            return None
        day = min(self.days, key=lambda day: (-self.days[day], day))
        return day, self.days[day]


def _ring(multiplier: int) -> str:
    if multiplier == 0:
        return "miss"
    return {1: "single", 2: "double", 3: "triple"}[multiplier]
