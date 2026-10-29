from collections import Counter
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.double_statistics import (
    DoubleStatistics,
    MissDirection,
)
from app.api.features.statistics.domain.player_statistics import (
    HEATMAP_CELL,
    PlayerStatistics,
    Scatter,
)


def _rounded(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def _directions(counts: Counter[MissDirection]) -> dict[MissDirection, int]:
    return {direction: counts[direction] for direction in MissDirection}


class DoubleDto(CamelModel):
    """Darts at one finishing double; throws are (x, y, hit) in board mm."""

    label: str
    attempts: int
    hits: int
    distance: float | None
    directions: dict[MissDirection, int]
    fields: dict[str, int]
    throws: list[tuple[float, float, bool]]

    @classmethod
    def from_entity(cls, double: DoubleStatistics) -> Self:
        located = double.located
        return cls(
            label=double.label,
            attempts=double.attempts,
            hits=double.hits,
            distance=_rounded(double.distance / located if located else None),
            directions=_directions(double.directions),
            fields=dict(double.fields),
            throws=[(round(t.x, 1), round(t.y, 1), t.hit) for t in double.throws],
        )


class ScatterDto(CamelModel):
    major: float
    minor: float
    angle: float

    @classmethod
    def from_entity(cls, scatter: Scatter) -> Self:
        return cls(
            major=round(scatter.major, 1),
            minor=round(scatter.minor, 1),
            angle=round(scatter.angle),
        )


class PlayerStatisticsDto(CamelModel):
    legs: int
    legs_won: int
    darts: int
    points: int
    average: float
    first_nine_average: float
    best_visit: int
    highest_finish: int
    visits180: int
    visits140_plus: int
    visits100_plus: int
    visits60_plus: int
    checkout_attempts: int
    checkout_hits: int
    fields: dict[str, int]
    located_fields: dict[str, int]
    heatmap: list[tuple[int, int, int]]
    doubles: list[DoubleDto]
    double_distance: float | None
    miss_directions: dict[MissDirection, int]
    grouping: float | None
    grouping_darts: int
    scatter: ScatterDto | None
    dart_averages: list[float | None]

    @classmethod
    def from_entity(cls, statistics: PlayerStatistics) -> Self:
        scatter = statistics.scatter
        return cls(
            legs=statistics.legs,
            legs_won=statistics.legs_won,
            darts=statistics.darts,
            points=statistics.points,
            average=round(statistics.average, 2),
            first_nine_average=round(statistics.first_nine_average, 2),
            best_visit=statistics.best_visit,
            highest_finish=statistics.highest_finish,
            visits180=statistics.visits_180,
            visits140_plus=statistics.visits_140_plus,
            visits100_plus=statistics.visits_100_plus,
            visits60_plus=statistics.visits_60_plus,
            checkout_attempts=statistics.checkout_attempts,
            checkout_hits=statistics.checkout_hits,
            fields=dict(statistics.fields),
            located_fields=dict(statistics.located_fields),
            heatmap=[
                (column * HEATMAP_CELL, row * HEATMAP_CELL, count)
                for (column, row), count in statistics.heatmap.items()
            ],
            doubles=[
                DoubleDto.from_entity(double)
                for double in sorted(statistics.doubles.values(), key=lambda d: -d.attempts)
            ],
            double_distance=_rounded(statistics.double_distance),
            miss_directions=_directions(statistics.miss_directions),
            grouping=_rounded(statistics.grouping),
            grouping_darts=statistics.grouping_darts,
            scatter=None if scatter is None else ScatterDto.from_entity(scatter),
            dart_averages=[_rounded(value, 2) for value in statistics.dart_averages],
        )
