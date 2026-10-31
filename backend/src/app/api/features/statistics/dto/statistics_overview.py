from typing import Self

from app.api.features.statistics.domain.overview import StatisticsOverview
from app.api.features.statistics.dto.player_statistics import PlayerStatisticsDto
from app.api.features.statistics.dto.trend_point import TrendPointDto


class StatisticsOverviewDto(PlayerStatisticsDto):
    """The tally with its games one by one, oldest first, for the trend."""

    trend: list[TrendPointDto]

    @classmethod
    def from_overview(cls, overview: StatisticsOverview) -> Self:
        totals = PlayerStatisticsDto.from_entity(overview.totals)
        return cls(
            **dict(totals),
            trend=[TrendPointDto.from_entity(point) for point in overview.trend],
        )
