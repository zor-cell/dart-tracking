from datetime import date
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.overall_statistics import OverallStatistics
from app.api.features.statistics.dto.hit_pattern import HitPatternDto, hit_pattern


class WeekDto(CamelModel):
    # The Monday the week starts on.
    week: date
    darts: int


class DayDto(CamelModel):
    day: date
    darts: int


class OverallStatisticsDto(HitPatternDto):
    """Every finished game of any kind: how much, where the darts went and when."""

    games: int
    darts: int
    seconds: int
    games_with_opponent: int
    wins: int
    misses: int
    located: int
    # Games per variant.
    variants: dict[str, int]
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: dict[str, int]
    # Oldest first, the weeks without a dart included.
    weeks: list[WeekDto]
    longest_streak: int
    busiest_day: DayDto | None

    @classmethod
    def from_entity(cls, statistics: OverallStatistics) -> Self:
        busiest = statistics.busiest_day
        return cls(
            games=statistics.games,
            darts=statistics.darts,
            seconds=round(statistics.seconds),
            games_with_opponent=statistics.games_with_opponent,
            wins=statistics.wins,
            misses=statistics.misses,
            located=statistics.located,
            variants=dict(statistics.variants),
            **hit_pattern(statistics.hits),
            rings=dict(statistics.rings),
            weeks=[WeekDto(week=week, darts=darts) for week, darts in statistics.weeks],
            longest_streak=statistics.longest_streak,
            busiest_day=None if busiest is None else DayDto(day=busiest[0], darts=busiest[1]),
        )
