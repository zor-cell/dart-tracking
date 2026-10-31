"""The selected games in one tally and one by one, as the statistics page shows them."""

from dataclasses import dataclass

from app.api.features.statistics.domain.player_statistics import PlayerStatistics
from app.api.features.statistics.domain.trend import TrendPoint


@dataclass(frozen=True)
class StatisticsOverview:
    totals: PlayerStatistics
    # The same games tallied each on its own, oldest first.
    trend: list[TrendPoint]
