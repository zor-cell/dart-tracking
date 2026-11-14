from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.cricket import (
    CRICKET_TARGETS,
    CricketProgress,
    CricketScoring,
)
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant


class CricketSettingsDto(CamelModel):
    variant: Literal[GameVariant.CRICKET] = GameVariant.CRICKET
    scoring: CricketScoring = CricketScoring.STANDARD


class CricketPlayerDto(CamelModel):
    # Marks per target, in the order of `CricketStateDto.targets`, three at most.
    marks: list[int]
    points: int
    # Counted marks per three darts; None before the first dart.
    marks_per_round: float | None
    # Counted marks of the last closed visit; None before it.
    last_visit: int | None


class CricketStandingDto(CamelModel):
    variant: Literal[GameVariant.CRICKET] = GameVariant.CRICKET
    targets: list[int]
    # One per player, in seat order.
    players: list[CricketPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, progress: CricketProgress) -> Self:
        players = []
        for player in game.players:
            standing = progress.players[player.id]
            last = game.last_closed_turn(player.id)
            players.append(
                CricketPlayerDto(
                    marks=[standing.marks[target] for target in CRICKET_TARGETS],
                    points=standing.points,
                    marks_per_round=(
                        round(3 * standing.counted_marks / standing.darts, 2)
                        if standing.darts
                        else None
                    ),
                    last_visit=None if last is None else progress.turn_marks[last],
                )
            )
        return cls(targets=list(CRICKET_TARGETS), players=players)
