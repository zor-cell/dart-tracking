from datetime import date
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.heatmap import cell_centres
from app.api.features.statistics.domain.overall_statistics import OverallStatistics


class WeekDto(CamelModel):
    # The Monday the week starts on.
    week: date
    darts: int


class DayDto(CamelModel):
    day: date
    darts: int


class RivalDto(CamelModel):
    player_id: str
    name: str
    games: int
    wins: int
    losses: int


class OverallStatisticsDto(CamelModel):
    """Every finished game of any kind: how much, where the darts went, when and against whom."""

    games: int
    darts: int
    seconds: int
    games_with_opponent: int
    wins: int
    misses: int
    located: int
    # Games per variant.
    variants: dict[str, int]
    # Darts per called-out label, a miss as 0; the located ones apart, as the heatmaps take them.
    fields: dict[str, int]
    located_fields: dict[str, int]
    # Centre of each heatmap cell in board mm and its located darts.
    heatmap: list[tuple[int, int, int]]
    # Darts per ring: single (the 25 too), double (the bull too), triple, miss.
    rings: dict[str, int]
    # Oldest first, the weeks without a dart included.
    weeks: list[WeekDto]
    longest_streak: int
    busiest_day: DayDto | None
    opponents: int
    rival: RivalDto | None

    @classmethod
    def from_entity(cls, statistics: OverallStatistics) -> Self:
        busiest = statistics.busiest_day
        rival = statistics.rival
        return cls(
            games=statistics.games,
            darts=statistics.darts,
            seconds=round(statistics.seconds),
            games_with_opponent=statistics.games_with_opponent,
            wins=statistics.wins,
            misses=statistics.misses,
            located=statistics.located,
            variants=dict(statistics.variants),
            fields=dict(statistics.fields),
            located_fields=dict(statistics.located_fields),
            heatmap=cell_centres(statistics.cells),
            rings=dict(statistics.rings),
            weeks=[WeekDto(week=week, darts=darts) for week, darts in statistics.weeks],
            longest_streak=statistics.longest_streak,
            busiest_day=None if busiest is None else DayDto(day=busiest[0], darts=busiest[1]),
            opponents=len(statistics.opponents),
            rival=None
            if rival is None
            else RivalDto(
                player_id=rival[0],
                name=rival[1].name,
                games=rival[1].games,
                wins=rival[1].wins,
                losses=rival[1].losses,
            ),
        )
