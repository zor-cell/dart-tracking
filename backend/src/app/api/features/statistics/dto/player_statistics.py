from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.player_statistics import (
    PlayerStatistics,
    Scatter,
    VisitRef,
)
from app.api.features.statistics.dto.hit_pattern import HitPatternDto, hit_pattern
from app.api.features.statistics.dto.target_statistics import FieldTallyDto


def _rounded(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


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


class VisitRefDto(CamelModel):
    """A visit to open in its game's replay; `visit` counts the game's visits with darts."""

    game_id: str
    visit: int

    @classmethod
    def from_entity(cls, ref: VisitRef | None) -> Self | None:
        return None if ref is None else cls(game_id=ref.game_id, visit=ref.visit)


class PlayerStatisticsDto(HitPatternDto):
    legs: int
    legs_won: int
    # Legs against someone else, and those of them won.
    duel_legs: int
    duel_legs_won: int
    darts: int
    darts_per_leg: float | None
    # The fewest darts a won leg took, and where it was finished.
    fewest_darts: int | None
    fewest_darts_at: VisitRefDto | None
    points: int
    average: float
    first_nine_average: float
    best_visit: int
    highest_finish: int
    best_visit_at: VisitRefDto | None
    highest_finish_at: VisitRefDto | None
    favourite_visit: int | None
    # The finish thrown most often; null without a won leg.
    favourite_finish: int | None
    visit_scores: dict[int, int]
    visits180: int
    visits140_plus: int
    visits100_plus: int
    visits60_plus: int
    checkout_attempts: int
    checkout_hits: int
    doubles: list[FieldTallyDto]
    double_distance: float | None
    grouping: float | None
    grouping_darts: int
    scoring_darts: int
    scatter: ScatterDto | None
    dart_averages: list[float | None]

    @classmethod
    def from_entity(cls, statistics: PlayerStatistics) -> Self:
        scatter = statistics.scatter
        return cls(
            legs=statistics.legs,
            legs_won=statistics.legs_won,
            duel_legs=statistics.duel_legs,
            duel_legs_won=statistics.duel_legs_won,
            darts=statistics.darts,
            darts_per_leg=_rounded(statistics.darts_per_leg),
            fewest_darts=statistics.fewest_darts,
            fewest_darts_at=VisitRefDto.from_entity(statistics.fewest_darts_at),
            points=statistics.points,
            average=round(statistics.average, 2),
            first_nine_average=round(statistics.first_nine_average, 2),
            best_visit=statistics.best_visit,
            highest_finish=statistics.highest_finish,
            best_visit_at=VisitRefDto.from_entity(statistics.best_visit_at),
            highest_finish_at=VisitRefDto.from_entity(statistics.highest_finish_at),
            favourite_visit=statistics.favourite_visit,
            favourite_finish=statistics.favourite_finish,
            visit_scores=dict(statistics.visit_scores),
            visits180=statistics.visits_180,
            visits140_plus=statistics.visits_140_plus,
            visits100_plus=statistics.visits_100_plus,
            visits60_plus=statistics.visits_60_plus,
            checkout_attempts=statistics.checkout_attempts,
            checkout_hits=statistics.checkout_hits,
            **hit_pattern(statistics.hits),
            doubles=[
                FieldTallyDto.from_double(double)
                for double in sorted(statistics.doubles.values(), key=lambda d: -d.attempts)
            ],
            double_distance=_rounded(statistics.double_distance),
            grouping=_rounded(statistics.grouping),
            grouping_darts=statistics.grouping_darts,
            scoring_darts=statistics.scoring_darts,
            scatter=None if scatter is None else ScatterDto.from_entity(scatter),
            dart_averages=[_rounded(value, 2) for value in statistics.dart_averages],
        )
