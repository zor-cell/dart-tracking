from collections.abc import Sequence
from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.personal_training import (
    PersonalFocus,
    PersonalLength,
    PersonalOptions,
    PersonalProgress,
    PlanBlock,
)
from app.api.features.game.domain.training import Field, TrainingMinutes
from app.api.features.game.dto.training import TrainingFieldDto, seconds_left
from app.api.features.game.services.personal_plan import PersonalPlan
from app.api.features.statistics.domain.weakness import Weakness


class PersonalSettingsDto(CamelModel):
    variant: Literal[GameVariant.PERSONAL] = GameVariant.PERSONAL
    focus: PersonalFocus = PersonalFocus.ALL
    length: PersonalLength = PersonalLength.MEDIUM
    # Whether a single is hit by its double and triple too.
    any_ring: bool = True
    # Minutes the plan runs from its first dart; None plays it by darts.
    minutes: TrainingMinutes | None = None

    @classmethod
    def of(cls, options: PersonalOptions) -> Self:
        return cls(
            focus=options.focus,
            length=options.length,
            any_ring=options.any_ring,
            minutes=options.minutes,
        )


class PlanBlockDto(CamelModel):
    # One field, or every planned field in turn.
    fields: list[TrainingFieldDto]
    darts: int

    @classmethod
    def from_entity(cls, block: PlanBlock) -> Self:
        return cls(fields=[_field(target) for target in block.fields], darts=block.darts)


class TallyDto(CamelModel):
    darts: int
    hits: int


class FieldRecordDto(TrainingFieldDto):
    darts: int
    hits: int


class PlannedFieldDto(FieldRecordDto):
    # The ring's darts and hits over every field: the player's average there.
    ring_darts: int
    ring_hits: int
    # Whether enough darts tell the rate; a thin field is in the plan to learn it.
    telling: bool


class LengthPlanDto(CamelModel):
    length: PersonalLength
    blocks: list[PlanBlockDto]


class FocusPlanDto(CamelModel):
    focus: PersonalFocus
    # The planned fields' records, in plan order.
    fields: list[PlannedFieldDto]
    lengths: list[LengthPlanDto]


class PersonalPlanDto(CamelModel):
    """What the plans are drawn from, and the plan a training of each focus and length
    would start on now."""

    games: int
    darts: int
    foci: list[FocusPlanDto]

    @classmethod
    def from_entity(cls, plans: Sequence[PersonalPlan]) -> Self:
        foci: dict[PersonalFocus, FocusPlanDto] = {}
        for plan in plans:
            options = plan.options
            focus = foci.setdefault(
                options.focus,
                FocusPlanDto(
                    focus=options.focus, fields=[_planned(weak) for weak in plan.fields], lengths=[]
                ),
            )
            focus.lengths.append(
                LengthPlanDto(
                    length=options.length,
                    blocks=[PlanBlockDto.from_entity(block) for block in options.blocks],
                )
            )
        return cls(
            games=plans[0].games if plans else 0,
            darts=plans[0].darts if plans else 0,
            foci=list(foci.values()),
        )


class PersonalPlayerDto(CamelModel):
    # The block under way; the number of blocks once the plan is through.
    block: int
    # The field to hit next; None once the plan is through.
    target: TrainingFieldDto | None
    # Darts the block under way still takes.
    left: int
    darts: int
    hits: int
    # Hits of the last closed visit; None before it.
    last_visit: int | None
    # Darts and hits per block, in plan order.
    blocks: list[TallyDto]
    # Today's darts and hits per planned field.
    fields: list[FieldRecordDto]


class PersonalStandingDto(CamelModel):
    variant: Literal[GameVariant.PERSONAL] = GameVariant.PERSONAL
    blocks: list[PlanBlockDto]
    # Each planned field's record before the training.
    baselines: list[FieldRecordDto]
    # One per player, in seat order.
    players: list[PersonalPlayerDto]
    # Seconds of a timed plan left when this was sent; None by darts or before the first dart.
    seconds_left: float | None = None

    @classmethod
    def from_entity(cls, game: Game, progress: PersonalProgress) -> Self:
        options = game.options
        if not isinstance(options, PersonalOptions):
            raise ValueError("not a personal training")
        players = []
        for player in game.players:
            standing = progress.players[player.id]
            last = game.last_closed_turn(player.id)
            players.append(
                PersonalPlayerDto(
                    block=standing.block,
                    target=None if standing.target is None else _field(standing.target),
                    left=standing.left,
                    darts=standing.darts,
                    hits=standing.hits,
                    last_visit=None if last is None else progress.turn_hits[last],
                    blocks=[
                        TallyDto(darts=tally.darts, hits=tally.hits)
                        for tally in standing.blocks
                    ],
                    fields=[
                        _record(target, tally.darts, tally.hits)
                        for target, tally in standing.fields.items()
                    ],
                )
            )
        return cls(
            blocks=[PlanBlockDto.from_entity(block) for block in options.blocks],
            baselines=[
                _record(baseline.field, baseline.darts, baseline.hits)
                for baseline in options.baselines
            ],
            players=players,
            seconds_left=seconds_left(options.minutes, game.turns),
        )


def _planned(weak: Weakness) -> PlannedFieldDto:
    return PlannedFieldDto(
        value=weak.target.value,
        multiplier=weak.target.multiplier or 1,
        darts=weak.darts,
        hits=weak.hits,
        ring_darts=weak.ring_darts,
        ring_hits=weak.ring_hits,
        telling=weak.telling,
    )


def _field(target: Field) -> TrainingFieldDto:
    return TrainingFieldDto(value=target[0], multiplier=target[1])


def _record(target: Field, darts: int, hits: int) -> FieldRecordDto:
    return FieldRecordDto(value=target[0], multiplier=target[1], darts=darts, hits=hits)
