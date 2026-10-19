from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.player_statistics import PlayerStatistics

# Enough points for a heatmap to be readable; beyond that it is a black disc.
_HEATMAP_LIMIT = 2000


class PlayerStatisticsDto(CamelModel):
    legs: int
    legs_won: int
    darts: int
    points: int
    average: float
    first_nine_average: float
    best_visit: int
    visits180: int
    visits100_plus: int
    checkout_chances: int
    double_attempts: int
    double_hits: int
    heatmap: list[tuple[float, float]]

    @classmethod
    def from_entity(cls, statistics: PlayerStatistics) -> Self:
        return cls(
            legs=statistics.legs,
            legs_won=statistics.legs_won,
            darts=statistics.darts,
            points=statistics.points,
            average=round(statistics.average, 2),
            first_nine_average=round(statistics.first_nine_average, 2),
            best_visit=statistics.best_visit,
            visits180=statistics.visits_180,
            visits100_plus=statistics.visits_100_plus,
            checkout_chances=statistics.checkout_chances,
            double_attempts=statistics.double_attempts,
            double_hits=statistics.double_hits,
            heatmap=statistics.heatmap[-_HEATMAP_LIMIT:],
        )
