from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.player_statistics import (
    HEATMAP_CELL,
    PlayerStatistics,
)


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
    fields: dict[str, int]
    heatmap: list[tuple[int, int, int]]

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
            fields=dict(statistics.fields),
            heatmap=[
                (column * HEATMAP_CELL, row * HEATMAP_CELL, count)
                for (column, row), count in statistics.heatmap.items()
            ],
        )
