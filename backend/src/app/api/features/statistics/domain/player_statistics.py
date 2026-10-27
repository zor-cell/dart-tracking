"""What a player's throws add up to. The rules live here rather than in SQL:
bust and checkout are decided in the game domain, and a second copy of them in a
query would be a second truth."""

import math
from collections import Counter
from dataclasses import dataclass, field

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.turn import Turn
from app.api.features.statistics.domain.double_statistics import (
    BULL,
    DoubleStatistics,
    MissDirection,
)

# A visit worth calling out, the way a scoreboard does.
_HIGH_VISIT = 100

# The highest score one visit can finish; above it every dart aims to score.
_HIGHEST_FINISH = 170

# The opening darts of a leg, before the checkout changes how a player aims.
_FIRST_NINE = 9

# Edge of a heatmap cell, in board millimetres.
HEATMAP_CELL = 2


# Scores one dart can finish on: the doubles and the double bull in double out,
# any field in single out.
_DOUBLE_FINISHES = frozenset({*range(2, 41, 2), 50})
_SINGLE_FINISHES = frozenset({*range(1, 21), *range(2, 41, 2), *range(3, 61, 3), 25, 50})

_DARTS_PER_VISIT = 3


@dataclass(frozen=True)
class Scatter:
    """How the darts of a visit spread around its middle, as an ellipse in board mm."""

    major: float  # standard deviation along the wider axis
    minor: float
    angle: float  # degrees of the wider axis, counter-clockwise from +x


@dataclass
class PlayerStatistics:
    """Totals over every counted leg. The rates are left as pairs rather than
    percentages so they stay addable and say how thin the sample is."""

    legs: int = 0
    legs_won: int = 0
    darts: int = 0
    points: int = 0
    best_visit: int = 0
    visits_180: int = 0
    visits_100_plus: int = 0
    legs_with_chance: int = 0
    checkout_attempts: int = 0
    checkout_hits: int = 0
    first_nine_darts: int = 0
    first_nine_points: int = 0
    fields: Counter[str] = field(default_factory=Counter)
    heatmap: Counter[tuple[int, int]] = field(default_factory=Counter)
    doubles: dict[int, DoubleStatistics] = field(default_factory=dict)
    # Located darts of scoring visits, measured from their visit's middle.
    grouping_darts: int = 0
    grouping_distance: float = 0.0
    spread: tuple[float, float, float] = (0.0, 0.0, 0.0)  # summed dx², dy², dx·dy
    # Points and darts of scoring visits by the dart's place in the visit.
    dart_points: list[int] = field(default_factory=lambda: [0] * _DARTS_PER_VISIT)
    dart_counts: list[int] = field(default_factory=lambda: [0] * _DARTS_PER_VISIT)

    @property
    def average(self) -> float:
        """Points per three darts — the number a scoreboard shows."""
        return 0.0 if self.darts == 0 else 3 * self.points / self.darts

    @property
    def first_nine_average(self) -> float:
        """Points per three darts over each leg's first nine darts."""
        if self.first_nine_darts == 0:
            return 0.0
        return 3 * self.first_nine_points / self.first_nine_darts

    @property
    def grouping(self) -> float | None:
        """Mean distance (mm) of a dart from the middle of its scoring visit."""
        return None if self.grouping_darts == 0 else self.grouping_distance / self.grouping_darts

    @property
    def scatter(self) -> Scatter | None:
        if self.grouping_darts == 0:
            return None
        xx, yy, xy = (value / self.grouping_darts for value in self.spread)
        mean, half = (xx + yy) / 2, math.hypot((xx - yy) / 2, xy)
        return Scatter(
            major=math.sqrt(mean + half),
            minor=math.sqrt(max(mean - half, 0.0)),
            angle=math.degrees(math.atan2(2 * xy, xx - yy) / 2),
        )

    @property
    def dart_averages(self) -> list[float | None]:
        """Points per dart by its place in a scoring visit."""
        return [
            None if count == 0 else points / count
            for points, count in zip(self.dart_points, self.dart_counts, strict=True)
        ]

    @property
    def double_miss_distance(self) -> float | None:
        """Mean distance (mm) of a located miss from the double it was thrown at."""
        located = sum(double.located_misses for double in self.doubles.values())
        if located == 0:
            return None
        return sum(double.miss_distance for double in self.doubles.values()) / located

    @property
    def double_misses_located(self) -> int:
        return sum(double.located_misses for double in self.doubles.values())

    @property
    def miss_directions(self) -> Counter[MissDirection]:
        return sum((double.directions for double in self.doubles.values()), Counter())

    def add_leg(self, mode: int, checkout_mode: CheckoutMode, turns: list[Turn]) -> None:
        finishes = (
            _DOUBLE_FINISHES if checkout_mode is CheckoutMode.DOUBLE_OUT else _SINGLE_FINISHES
        )
        remaining = mode
        had_chance = False
        thrown = 0

        for turn in turns:
            # What the player faced at the oche, which is what a chance is
            # measured against — the visit's own outcome comes after.
            if remaining <= _HIGHEST_FINISH:
                had_chance = True
            elif not turn.busted:
                self._add_scoring_visit(turn)

            live = remaining
            for dart in turn.darts:
                self.darts += 1
                self.fields[dart.label] += 1
                thrown += 1
                if thrown <= _FIRST_NINE:
                    self.first_nine_darts += 1
                    if not turn.busted:
                        self.first_nine_points += dart.points
                if live in finishes:
                    self.checkout_attempts += 1
                    if checkout_mode is CheckoutMode.DOUBLE_OUT:
                        hit = dart.multiplier == 2 and dart.points == live
                        self._add_double_attempt(live, hit, dart.position)
                live -= dart.points
                if live == 0 and not turn.busted:
                    self.checkout_hits += 1
                if dart.position is not None:
                    x, y = dart.position
                    self.heatmap[round(x / HEATMAP_CELL), round(y / HEATMAP_CELL)] += 1

            if turn.busted:
                continue

            self.points += turn.points
            remaining -= turn.points
            self.best_visit = max(self.best_visit, turn.points)
            if turn.points == 180:
                self.visits_180 += 1
            if turn.points >= _HIGH_VISIT:
                self.visits_100_plus += 1

        self.legs += 1
        if had_chance:
            self.legs_with_chance += 1
        if remaining == 0:
            self.legs_won += 1

    def _add_scoring_visit(self, turn: Turn) -> None:
        for place, dart in enumerate(turn.darts[:_DARTS_PER_VISIT]):
            self.dart_points[place] += dart.points
            self.dart_counts[place] += 1

        located = [dart.position for dart in turn.darts if dart.position is not None]
        if len(located) < 2:
            return
        mid_x = sum(x for x, _ in located) / len(located)
        mid_y = sum(y for _, y in located) / len(located)
        xx, yy, xy = self.spread
        for x, y in located:
            dx, dy = x - mid_x, y - mid_y
            self.grouping_darts += 1
            self.grouping_distance += math.hypot(dx, dy)
            xx, yy, xy = xx + dx * dx, yy + dy * dy, xy + dx * dy
        self.spread = (xx, yy, xy)

    def _add_double_attempt(
        self, live: int, hit: bool, position: tuple[float, float] | None
    ) -> None:
        value = BULL if live == 50 else live // 2
        self.doubles.setdefault(value, DoubleStatistics(value)).add(hit, position)
