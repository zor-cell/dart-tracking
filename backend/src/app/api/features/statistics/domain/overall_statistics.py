"""Everything a player threw, whatever the game: how much, where, when and against whom."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.api.features.game.domain.game import Game
from app.api.features.statistics.domain.heatmap import heatmap_cell


@dataclass
class OpponentTally:
    name: str
    games: int = 0
    # Games the player won against this opponent, and games the opponent won.
    wins: int = 0
    losses: int = 0


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
    # Darts per called-out label, a miss as 0, and the located ones per label and cell.
    fields: Counter[str] = field(default_factory=Counter)
    located_fields: Counter[str] = field(default_factory=Counter)
    cells: Counter[tuple[int, int]] = field(default_factory=Counter)
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: Counter[str] = field(default_factory=Counter)
    # Darts per day the games were played on.
    days: Counter[date] = field(default_factory=Counter)
    # Keyed by the opponent's player id.
    opponents: dict[str, OpponentTally] = field(default_factory=dict)

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
            self.fields[dart.label] += 1
            self.rings[_ring(dart.multiplier)] += 1
            self.misses += dart.multiplier == 0
            if dart.position is not None:
                self.located += 1
                self.located_fields[dart.label] += 1
                self.cells[heatmap_cell(*dart.position)] += 1
        others = [player for player in game.players if player.id != seat]
        if not others:
            return
        self.games_with_opponent += 1
        winner = game.winner
        won = winner is not None and winner.id == seat
        self.wins += won
        for other in others:
            tally = self.opponents.setdefault(other.identity_id, OpponentTally(other.name))
            tally.games += 1
            tally.wins += won
            tally.losses += winner is not None and winner.id == other.id

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

    @property
    def rival(self) -> tuple[str, OpponentTally] | None:
        """The opponent met most often, ahead of a tie the one named first."""
        if not self.opponents:
            return None
        return min(self.opponents.items(), key=lambda entry: (-entry[1].games, entry[1].name))


def _ring(multiplier: int) -> str:
    if multiplier == 0:
        return "miss"
    return {1: "single", 2: "double", 3: "triple"}[multiplier]
