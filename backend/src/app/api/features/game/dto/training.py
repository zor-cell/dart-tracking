from random import randrange
from typing import Self

from pydantic import Field, model_validator

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.training import (
    MAX_REPEATS,
    TrainingGoal,
    TrainingOptions,
    TrainingProgress,
    TrainingRing,
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


class TrainingOptionsDto(CamelModel):
    goal: TrainingGoal = TrainingGoal.FREE
    ring: TrainingRing = TrainingRing.SINGLE
    fields: list[TrainingFieldDto] = Field(default_factory=list)
    # Hits a target takes before the next one comes up.
    repeats: int = Field(1, ge=1, le=MAX_REPEATS)
    # Whether the own fields come up at random rather than in order.
    shuffle: bool = False

    @model_validator(mode="after")
    def _fields_chosen(self) -> Self:
        chosen = [(field.value, field.multiplier) for field in self.fields]
        if self.goal is TrainingGoal.FIELDS and not chosen:
            raise ValueError("own fields need at least one field")
        if len(set(chosen)) != len(chosen):
            raise ValueError("a field can be chosen once")
        return self

    def to_entity(self) -> TrainingOptions:
        """Draws the seed the random targets follow from."""
        return TrainingOptions(
            goal=self.goal,
            ring=self.ring,
            fields=tuple((field.value, field.multiplier) for field in self.fields),
            repeats=self.repeats,
            shuffle=self.shuffle,
            seed=randrange(2**31),
        )

    @classmethod
    def of(cls, options: TrainingOptions) -> Self:
        return cls(
            goal=options.goal,
            ring=options.ring,
            fields=_fields(options.fields),
            repeats=options.repeats,
            shuffle=options.shuffle,
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


class TrainingStateDto(TrainingOptionsDto):
    # One per player, in seat order.
    players: list[TrainingPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, options: TrainingOptions, progress: TrainingProgress) -> Self:
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
        return cls(**TrainingOptionsDto.of(options).model_dump(), players=players)


def _fields(fields: tuple[tuple[int, int], ...] | list[tuple[int, int]]) -> list[TrainingFieldDto]:
    return [TrainingFieldDto(value=value, multiplier=multiplier) for value, multiplier in fields]
