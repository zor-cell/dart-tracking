"""How much was played when: darts, games and time per variant, cut into days, weeks or months."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from app.api.features.game.domain.game_variant import GameVariant

# The longest span shown in days, and in weeks; anything longer is shown in months.
DAYS_UP_TO = 31
WEEKS_UP_TO = 122


class ActivityUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class ActivityTally:
    darts: int = 0
    games: int = 0
    # From setting the games up to their end.
    seconds: float = 0.0

    def add(self, other: "ActivityTally") -> None:
        self.darts += other.darts
        self.games += other.games
        self.seconds += other.seconds


@dataclass(frozen=True)
class ActivityBucket:
    # The day, the Monday or the first of the month the bucket starts on.
    start: date
    variants: dict[GameVariant, ActivityTally] = field(default_factory=dict)


@dataclass(frozen=True)
class Activity:
    unit: ActivityUnit
    buckets: list[ActivityBucket]


def activity(
    days: Mapping[tuple[date, GameVariant], ActivityTally], first: date, last: date
) -> Activity:
    """The tallies from `first` to `last` in buckets of a unit that fits the span, empty ones too."""
    span = (last - first).days + 1
    unit = (
        ActivityUnit.DAY
        if span <= DAYS_UP_TO
        else ActivityUnit.WEEK
        if span <= WEEKS_UP_TO
        else ActivityUnit.MONTH
    )
    buckets: dict[date, ActivityBucket] = {}
    start = _start(first, unit)
    while start <= last:
        buckets[start] = ActivityBucket(start)
        start = _next(start, unit)
    for (day, variant), tally in days.items():
        bucket = buckets.get(_start(day, unit))
        if bucket is not None:
            bucket.variants.setdefault(variant, ActivityTally()).add(tally)
    return Activity(unit, list(buckets.values()))


def _start(day: date, unit: ActivityUnit) -> date:
    if unit is ActivityUnit.DAY:
        return day
    if unit is ActivityUnit.WEEK:
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _next(start: date, unit: ActivityUnit) -> date:
    if unit is ActivityUnit.DAY:
        return start + timedelta(days=1)
    if unit is ActivityUnit.WEEK:
        return start + timedelta(weeks=1)
    return (start + timedelta(days=32)).replace(day=1)
