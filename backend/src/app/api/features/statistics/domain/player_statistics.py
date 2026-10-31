"""What a player's throws add up to. The rules live here rather than in SQL:
bust and checkout are decided in the game domain, and a second copy of them in a
query would be a second truth."""

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.turn import Turn
from app.api.features.statistics.domain.double_statistics import BULL, DoubleStatistics
from app.api.features.statistics.domain.heatmap import heatmap_cell

# The highest score one visit can finish; above it every dart aims to score.
_HIGHEST_FINISH = 170

# The opening darts of a leg, before the checkout changes how a player aims.
_FIRST_NINE = 9


# Scores one dart can finish on: the doubles and the double bull in double out,
# any field in single out.
_DOUBLE_FINISHES = frozenset({*range(2, 41, 2), 50})
_SINGLE_FINISHES = frozenset({*range(1, 21), *range(2, 41, 2), *range(3, 61, 3), 25, 50})

_DARTS_PER_VISIT = 3


@dataclass(frozen=True)
class Scatter:
    """How the darts of a visit spread around each other, as an ellipse in board mm."""

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
    highest_finish: int = 0  # points of the best visit that won a leg
    visit_scores: Counter[int] = field(default_factory=Counter)  # scoring visits by points
    visits_180: int = 0
    visits_140_plus: int = 0
    visits_100_plus: int = 0
    visits_60_plus: int = 0
    checkout_attempts: int = 0
    checkout_hits: int = 0
    first_nine_darts: int = 0
    first_nine_points: int = 0
    fields: Counter[str] = field(default_factory=Counter)
    located_fields: Counter[str] = field(default_factory=Counter)  # fields of located darts only
    heatmap: Counter[tuple[int, int]] = field(default_factory=Counter)
    doubles: dict[int, DoubleStatistics] = field(default_factory=dict)
    # Located darts of scoring visits, and the pairs of two darts within one visit.
    grouping_darts: int = 0
    grouping_pairs: int = 0
    grouping_distance: float = 0.0  # summed mm between the two darts of each pair
    spread: tuple[float, float, float] = (0.0, 0.0, 0.0)  # pairs' summed dx², dy², dx·dy
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
    def scoring_darts(self) -> int:
        """Darts thrown in scoring visits, located or not."""
        return sum(self.dart_counts)

    @property
    def grouping(self) -> float | None:
        """Mean distance (mm) between two darts of a scoring visit."""
        return None if self.grouping_pairs == 0 else self.grouping_distance / self.grouping_pairs

    @property
    def scatter(self) -> Scatter | None:
        if self.grouping_pairs == 0:
            return None
        # A difference of two darts spreads twice as wide as one dart does.
        xx, yy, xy = (value / self.grouping_pairs / 2 for value in self.spread)
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
    def favourite_visit(self) -> int | None:
        """The score thrown most often, the higher one on a tie."""
        if not self.visit_scores:
            return None
        return max(self.visit_scores, key=lambda points: (self.visit_scores[points], points))

    @property
    def double_distance(self) -> float | None:
        """Mean distance (mm) of a located dart from the double it was thrown at, 0 for a hit."""
        located = self.double_darts_located
        if located == 0:
            return None
        return sum(double.distance for double in self.doubles.values()) / located

    @property
    def double_darts_located(self) -> int:
        return sum(double.located for double in self.doubles.values())

    def add_leg(self, mode: int, checkout_mode: CheckoutMode, turns: list[Turn]) -> None:
        finishes = (
            _DOUBLE_FINISHES if checkout_mode is CheckoutMode.DOUBLE_OUT else _SINGLE_FINISHES
        )
        remaining = mode
        thrown = 0

        for turn in turns:
            # What the player faced at the oche decides whether the visit aimed to score.
            if remaining > _HIGHEST_FINISH and not turn.busted:
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
                        self._add_double_attempt(live, hit, dart.label, dart.position)
                live -= dart.points
                if live == 0 and not turn.busted:
                    self.checkout_hits += 1
                if dart.position is not None:
                    x, y = dart.position
                    self.located_fields[dart.label] += 1
                    self.heatmap[heatmap_cell(x, y)] += 1

            if turn.busted:
                continue

            self.points += turn.points
            if turn.points > 0:
                self.visit_scores[turn.points] += 1
            remaining -= turn.points
            self.best_visit = max(self.best_visit, turn.points)
            if remaining == 0:
                self.highest_finish = max(self.highest_finish, turn.points)
            self._add_visit_band(turn.points)

        self.legs += 1
        if remaining == 0:
            self.legs_won += 1

    def _add_visit_band(self, points: int) -> None:
        """Counts a visit into every band it reaches: 60+, 100+ and 140+ include the 180s."""
        self.visits_180 += points == 180
        self.visits_140_plus += points >= 140
        self.visits_100_plus += points >= 100
        self.visits_60_plus += points >= 60

    def _add_scoring_visit(self, turn: Turn) -> None:
        for place, dart in enumerate(turn.darts[:_DARTS_PER_VISIT]):
            self.dart_points[place] += dart.points
            self.dart_counts[place] += 1

        located = [dart.position for dart in turn.darts if dart.position is not None]
        if len(located) < 2:
            return
        self.grouping_darts += len(located)
        xx, yy, xy = self.spread
        for (x1, y1), (x2, y2) in combinations(located, 2):
            dx, dy = x2 - x1, y2 - y1
            self.grouping_pairs += 1
            self.grouping_distance += math.hypot(dx, dy)
            xx, yy, xy = xx + dx * dx, yy + dy * dy, xy + dx * dy
        self.spread = (xx, yy, xy)

    def _add_double_attempt(
        self, live: int, hit: bool, scored: str, position: tuple[float, float] | None
    ) -> None:
        value = BULL if live == 50 else live // 2
        self.doubles.setdefault(value, DoubleStatistics(value)).add(hit, scored, position)
