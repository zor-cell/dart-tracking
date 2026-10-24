"""What a player's throws add up to. The rules live here rather than in SQL:
bust and checkout are decided in the game domain, and a second copy of them in a
query would be a second truth."""

from collections import Counter
from dataclasses import dataclass, field

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.turn import Turn

# A visit worth calling out, the way a scoreboard does.
_HIGH_VISIT = 100

# The opening darts of a leg, before the checkout changes how a player aims.
_FIRST_NINE = 9

# Edge of a heatmap cell, in board millimetres.
HEATMAP_CELL = 2


# Scores one dart can finish on: the doubles and the double bull in double out,
# any field in single out.
_DOUBLE_FINISHES = frozenset({*range(2, 41, 2), 50})
_SINGLE_FINISHES = frozenset({*range(1, 21), *range(2, 41, 2), *range(3, 61, 3), 25, 50})


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
            if remaining <= 170:
                had_chance = True

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
