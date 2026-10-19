"""What a player's throws add up to. The rules live here rather than in SQL:
bust and checkout are decided in the game domain, and a second copy of them in a
query would be a second truth."""

from dataclasses import dataclass, field

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.turn import Turn

# A visit worth calling out, the way a scoreboard does.
_HIGH_VISIT = 100

# The opening darts of a leg, before the checkout changes how a player aims.
_FIRST_NINE = 9


def _on_double(remaining: int) -> bool:
    """Whether a single dart at a double would finish from here — 50 is the
    double bull, everything else has to be an even number up to 40."""
    return remaining == 50 or (remaining <= 40 and remaining > 0 and remaining % 2 == 0)


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
    checkout_chances: int = 0
    double_attempts: int = 0
    double_hits: int = 0
    first_nine_darts: int = 0
    first_nine_points: int = 0
    heatmap: list[tuple[float, float]] = field(default_factory=list)

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
        double_out = checkout_mode is CheckoutMode.DOUBLE_OUT
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
                thrown += 1
                if thrown <= _FIRST_NINE:
                    self.first_nine_darts += 1
                    if not turn.busted:
                        self.first_nine_points += dart.points
                if double_out and _on_double(live):
                    self.double_attempts += 1
                live -= dart.points
                if live == 0 and not turn.busted and double_out:
                    self.double_hits += 1
                if dart.position is not None:
                    self.heatmap.append(dart.position)

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
            self.checkout_chances += 1
        if remaining == 0:
            self.legs_won += 1
