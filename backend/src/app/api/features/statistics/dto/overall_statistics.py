from datetime import date
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.statistics.domain.activity import (
    Activity,
    ActivityBucket,
    ActivityTally,
    ActivityUnit,
)
from app.api.features.statistics.domain.overall_statistics import OverallStatistics
from app.api.features.statistics.dto.hit_pattern import HitPatternDto, hit_pattern


class ActivityTallyDto(CamelModel):
    darts: int
    games: int
    seconds: int

    @classmethod
    def from_entity(cls, tally: ActivityTally) -> Self:
        return cls(darts=tally.darts, games=tally.games, seconds=round(tally.seconds))


class ActivityBucketDto(CamelModel):
    # The day, the Monday or the first of the month the bucket starts on.
    start: date
    # Only the variants played in it.
    variants: dict[GameVariant, ActivityTallyDto]

    @classmethod
    def from_entity(cls, bucket: ActivityBucket) -> Self:
        return cls(
            start=bucket.start,
            variants={
                variant: ActivityTallyDto.from_entity(tally)
                for variant, tally in bucket.variants.items()
            },
        )


class ActivityDto(CamelModel):
    unit: ActivityUnit
    # Oldest first, the empty ones included.
    buckets: list[ActivityBucketDto]

    @classmethod
    def from_entity(cls, activity: Activity) -> Self:
        return cls(
            unit=activity.unit,
            buckets=[ActivityBucketDto.from_entity(bucket) for bucket in activity.buckets],
        )


class OverallStatisticsDto(HitPatternDto):
    """Every finished game of any kind: how much, where the darts went and when."""

    games: int
    darts: int
    seconds: int
    games_with_opponent: int
    wins: int
    misses: int
    located: int
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: dict[str, int]
    # None without a game.
    activity: ActivityDto | None

    @classmethod
    def from_entity(cls, statistics: OverallStatistics) -> Self:
        activity = statistics.activity
        return cls(
            games=statistics.games,
            darts=statistics.darts,
            seconds=round(statistics.seconds),
            games_with_opponent=statistics.games_with_opponent,
            wins=statistics.wins,
            misses=statistics.misses,
            located=statistics.located,
            **hit_pattern(statistics.hits),
            rings=dict(statistics.rings),
            activity=None if activity is None else ActivityDto.from_entity(activity),
        )
