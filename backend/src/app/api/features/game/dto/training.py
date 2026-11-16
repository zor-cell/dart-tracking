from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.training import (
    MAX_REPEATS,
    TrainingGoal,
    TrainingLength,
    TrainingMinutes,
    TrainingOptions,
    TrainingProgress,
    TrainingRing,
    deadline,
)


class TrainingFieldDto(CamelModel):
    """A board field: 1 to 20 in any ring, or 25 as single (25) or double (bull)."""

    value: int = Field(ge=1, le=25)
    multiplier: int = Field(ge=1, le=3)

    @model_validator(mode="after")
    def _on_the_board(self) -> Self:
        if 20 < self.value < 25 or (self.value == 25 and self.multiplier == 3):
            raise ValueError("no such field")
        return self


class TrainingSettingsDto(CamelModel):
    variant: Literal[GameVariant.TRAINING] = GameVariant.TRAINING
    goal: TrainingGoal = TrainingGoal.FREE
    ring: TrainingRing = TrainingRing.SINGLE
    fields: list[TrainingFieldDto] = Field(default_factory=list)
    # Hits a target takes before the next one comes up.
    repeats: int = Field(1, ge=1, le=MAX_REPEATS)
    # Whether the own fields come up at random rather than in order.
    shuffle: bool = False
    # Whether any ring of a single field's number hits it.
    any_ring: bool = False
    # Darts per player or minutes the training runs; endless without both.
    darts: TrainingLength | None = None
    minutes: TrainingMinutes | None = None

    @model_validator(mode="after")
    def _fields_chosen(self) -> Self:
        chosen = [(field.value, field.multiplier) for field in self.fields]
        if self.goal is TrainingGoal.FIELDS and not chosen:
            raise ValueError("own fields need at least one field")
        if len(set(chosen)) != len(chosen):
            raise ValueError("a field can be chosen once")
        if self.darts is not None and self.minutes is not None:
            raise ValueError("a training ends by darts or by time")
        return self

    @classmethod
    def of(cls, options: TrainingOptions) -> Self:
        return cls(
            goal=options.goal,
            ring=options.ring,
            fields=_fields(options.fields),
            repeats=options.repeats,
            shuffle=options.shuffle,
            any_ring=options.any_ring,
            darts=options.darts,
            minutes=options.minutes,
        )


class TrainingTallyDto(TrainingFieldDto):
    darts: int
    hits: int


class TrainingPlayerDto(CamelModel):
    # The field to hit next; None without a target.
    target: TrainingFieldDto | None
    # Hits the target still takes before the next one comes up.
    left: int
    darts: int
    hits: int
    # Hits of the last closed visit; None before it.
    last_visit: int | None
    # Darts and hits per target, in the order the targets first came up.
    tallies: list[TrainingTallyDto]


class TrainingStandingDto(CamelModel):
    variant: Literal[GameVariant.TRAINING] = GameVariant.TRAINING
    # One per player, in seat order.
    players: list[TrainingPlayerDto]
    # Seconds of a timed training left when this was sent; None before its first dart.
    seconds_left: float | None

    @classmethod
    def from_entity(cls, game: Game, progress: TrainingProgress) -> Self:
        players = []
        for player in game.players:
            standing = progress.players[player.id]
            last = game.last_closed_turn(player.id)
            target = standing.target
            players.append(
                TrainingPlayerDto(
                    target=None if target is None else _fields([target])[0],
                    left=standing.left,
                    darts=standing.darts,
                    hits=standing.hits,
                    last_visit=None if last is None else progress.turn_hits[last],
                    tallies=[
                        TrainingTallyDto(
                            value=value, multiplier=multiplier, darts=tally.darts, hits=tally.hits
                        )
                        for (value, multiplier), tally in standing.tallies.items()
                    ],
                )
            )
        end = deadline(game.options, game.turns) if isinstance(game.options, TrainingOptions) else None
        left = None if end is None else max((end - datetime.now(UTC)).total_seconds(), 0.0)
        return cls(players=players, seconds_left=left)


def _fields(fields: tuple[tuple[int, int], ...] | list[tuple[int, int]]) -> list[TrainingFieldDto]:
    return [TrainingFieldDto(value=value, multiplier=multiplier) for value, multiplier in fields]
