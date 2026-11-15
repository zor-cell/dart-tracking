from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.target import Target
from app.api.features.statistics.domain.double_statistics import DoubleStatistics
from app.api.features.statistics.domain.heatmap import cell_centres
from app.api.features.statistics.domain.target_statistics import (
    FieldTally,
    GameTally,
    TargetStatistics,
    TargetTally,
)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


class TargetTallyDto(CamelModel):
    """Darts at a target; the rates stay pairs, so the view can weigh them."""

    darts: int
    hits: int
    located: int
    # Mean mm of the located darts from the target, a hit counting 0; null without any.
    distance: float | None

    @classmethod
    def of(cls, tally: TargetTally) -> dict[str, int | float | None]:
        return {
            "darts": tally.darts,
            "hits": tally.hits,
            "located": tally.located,
            "distance": _rounded(tally.mean_distance),
        }


class FieldTallyDto(TargetTallyDto):
    value: int
    # The ring that counts; null takes any ring of the number.
    multiplier: int | None
    located_hits: int
    # Darts per field they hit, by called-out label.
    fields: dict[str, int]
    # Centre of each heatmap cell in board mm and its located darts.
    cells: list[tuple[int, int, int]]

    @classmethod
    def from_entity(cls, target: Target, tally: FieldTally) -> Self:
        return cls(
            value=target.value,
            multiplier=target.multiplier,
            located_hits=tally.located_hits,
            fields=dict(tally.landed),
            cells=cell_centres(tally.cells),
            **cls.of(tally),
        )

    @classmethod
    def from_double(cls, double: DoubleStatistics) -> Self:
        located = double.located
        return cls(
            value=double.value,
            multiplier=2,
            darts=double.attempts,
            hits=double.hits,
            located=located,
            distance=_rounded(double.distance / located if located else None),
            located_hits=double.located_hits,
            fields=dict(double.fields),
            cells=cell_centres(double.cells),
        )


class GameTallyDto(TargetTallyDto):
    game_id: str
    played_at: datetime
    # Whether the player got through every target of the game.
    through: bool

    @classmethod
    def from_entity(cls, game: GameTally) -> Self:
        return cls(
            game_id=game.game_id, played_at=game.played_at, through=game.through, **cls.of(game)
        )


class TargetStatisticsDto(TargetTallyDto):
    """The darts thrown at named fields, in one tally, per field and game by game."""

    # Sorted by number, the bull last; within a number any ring first.
    fields: list[FieldTallyDto]
    # Oldest first.
    games: list[GameTallyDto]
    # Mean darts of the games the player got through; null without one.
    darts_to_finish: float | None
    best: GameTallyDto | None

    @classmethod
    def from_entity(cls, statistics: TargetStatistics) -> Self:
        return cls(**cls.overview(statistics))

    @classmethod
    def overview(cls, statistics: TargetStatistics) -> dict[str, object]:
        fields = sorted(
            statistics.fields.items(),
            key=lambda entry: (entry[0].value, entry[0].multiplier or 0),
        )
        best = statistics.best
        return {
            **cls.of(statistics.totals),
            "fields": [FieldTallyDto.from_entity(target, tally) for target, tally in fields],
            "games": [GameTallyDto.from_entity(game) for game in statistics.games],
            "darts_to_finish": _rounded(statistics.darts_to_finish),
            "best": None if best is None else GameTallyDto.from_entity(best),
        }
