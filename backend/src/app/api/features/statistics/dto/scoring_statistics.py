from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.scoring_statistics import ScoringGame, ScoringStatistics
from app.api.features.statistics.dto.hit_pattern import HitPatternDto, hit_pattern
from app.api.features.statistics.dto.player_statistics import VisitRefDto


class ScoringGameDto(CamelModel):
    game_id: str
    played_at: datetime
    darts: int
    average: float

    @classmethod
    def from_entity(cls, game: ScoringGame) -> Self:
        return cls(
            game_id=game.game_id,
            played_at=game.played_at,
            darts=game.darts,
            average=round(game.average, 2),
        )


class ScoringStatisticsDto(HitPatternDto):
    """The trainings without a target: their points, visit by visit and game by game."""

    darts: int
    average: float
    best_visit: int
    best_visit_at: VisitRefDto | None
    visits_180: int
    visits_140_plus: int
    visits_100_plus: int
    visits_60_plus: int
    # Visits by points.
    visit_scores: dict[int, int]
    # Oldest first.
    games: list[ScoringGameDto]

    @classmethod
    def from_entity(cls, statistics: ScoringStatistics) -> Self:
        return cls(
            darts=statistics.darts,
            average=round(statistics.average, 2),
            best_visit=statistics.best_visit,
            best_visit_at=VisitRefDto.from_entity(statistics.best_visit_at),
            visits_180=statistics.visits_from(180),
            visits_140_plus=statistics.visits_from(140),
            visits_100_plus=statistics.visits_from(100),
            visits_60_plus=statistics.visits_from(60),
            visit_scores=dict(statistics.visit_scores),
            games=[ScoringGameDto.from_entity(game) for game in statistics.games],
            **hit_pattern(statistics.hits),
        )
