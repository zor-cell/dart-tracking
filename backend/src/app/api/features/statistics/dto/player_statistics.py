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
    legs_with_chance: int
    checkout_attempts: int
    checkout_hits: int
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
            legs_with_chance=statistics.legs_with_chance,
            checkout_attempts=statistics.checkout_attempts,
            checkout_hits=statistics.checkout_hits,
            heatmap=statistics.heatmap[-_HEATMAP_LIMIT:],
        )
