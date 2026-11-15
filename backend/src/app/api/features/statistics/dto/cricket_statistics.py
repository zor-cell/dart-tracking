from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.cricket_statistics import CricketGame, CricketStatistics
from app.api.features.statistics.domain.heatmap import cell_centres
from app.api.features.statistics.dto.player_statistics import VisitRefDto


def _rounded(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


class CricketGameDto(CamelModel):
    game_id: str
    played_at: datetime
    won: bool
    darts: int
    marks: int
    # Marks per three darts; null without a dart.
    mpr: float | None
    # Mean mm of the located darts from the nearest number still open; null without any.
    distance: float | None

    @classmethod
    def from_entity(cls, game: CricketGame) -> Self:
        return cls(
            game_id=game.game_id,
            played_at=game.played_at,
            won=game.won,
            darts=game.darts,
            marks=game.marks,
            mpr=_rounded(game.mpr, 2),
            distance=_rounded(game.mean_distance),
        )


class CricketStatisticsDto(CamelModel):
    """Cricket over the selected games, in one tally and game by game."""

    darts: int
    marks: int
    mpr: float | None
    distance: float | None
    games_with_opponent: int
    wins: int
    empty: int
    # Visits by the marks they counted, keyed by the marks.
    visits: dict[int, int]
    best_visit: int
    best_visit_at: VisitRefDto | None
    favourite_visit: int | None
    # Oldest first.
    games: list[CricketGameDto]
    # Darts per called-out label; the located ones apart, as the heatmaps take them.
    fields: dict[str, int]
    located_fields: dict[str, int]
    # Centre of each heatmap cell in board mm and its located darts.
    heatmap: list[tuple[int, int, int]]

    @classmethod
    def from_entity(cls, statistics: CricketStatistics) -> Self:
        return cls(
            darts=statistics.darts,
            marks=statistics.marks,
            mpr=_rounded(statistics.mpr, 2),
            distance=_rounded(statistics.mean_distance),
            games_with_opponent=statistics.games_with_opponent,
            wins=statistics.wins,
            empty=statistics.empty,
            visits=dict(statistics.visits),
            best_visit=statistics.best_visit,
            best_visit_at=VisitRefDto.from_entity(statistics.best_visit_at),
            favourite_visit=statistics.favourite_visit,
            games=[CricketGameDto.from_entity(game) for game in statistics.games],
            fields=dict(statistics.fields),
            located_fields=dict(statistics.located_fields),
            heatmap=cell_centres(statistics.cells),
        )
