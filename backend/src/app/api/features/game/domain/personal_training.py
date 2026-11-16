"""Personal training: a fixed plan of blocks at the account's weakest fields, each a
set number of darts; the game is done once every planned dart is thrown."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

from app.api.features.game.domain.target import Target
from app.api.features.game.domain.training import Field
from app.api.features.game.domain.turn import Turn

# Weak fields a plan trains, each in a block of its own.
PLAN_FIELDS = 3
# Share of the darts the closing block spreads over every planned field.
MIXED_SHARE = 0.2
_VISIT = 3


class PersonalFocus(StrEnum):
    SINGLES = "singles"
    DOUBLES = "doubles"
    TRIPLES = "triples"
    ALL = "all"

    @property
    def rings(self) -> tuple[int | None, ...]:
        """The rings trained; None is the single, taken by every ring of its number."""
        return {"singles": (None,), "doubles": (2,), "triples": (3,), "all": (None, 2, 3)}[self.value]


class PersonalLength(IntEnum):
    """Darts in a plan; multiples of a visit, so a block never splits one."""

    SHORT = 45
    MEDIUM = 90
    LONG = 150


# Fields a plan fills up with while too few darts tell the weak ones, most played first.
PROBE_FIELDS: dict[PersonalFocus, tuple[Field, ...]] = {
    PersonalFocus.SINGLES: ((20, 1), (19, 1), (18, 1), (17, 1)),
    PersonalFocus.ALL: ((20, 2), (20, 3), (16, 2), (19, 3), (8, 2), (18, 3)),
    PersonalFocus.DOUBLES: ((20, 2), (16, 2), (8, 2), (10, 2), (18, 2), (25, 2)),
    PersonalFocus.TRIPLES: ((20, 3), (19, 3), (18, 3), (17, 3)),
}


@dataclass(frozen=True)
class PlanBlock:
    # One field, or every planned field in turn, dart by dart.
    fields: tuple[Field, ...]
    darts: int


@dataclass(frozen=True)
class Baseline:
    """A planned field's record before the training."""

    field: Field
    darts: int
    hits: int


@dataclass(frozen=True)
class PersonalOptions:
    focus: PersonalFocus = PersonalFocus.ALL
    length: PersonalLength = PersonalLength.MEDIUM
    blocks: tuple[PlanBlock, ...] = ()
    baselines: tuple[Baseline, ...] = ()
    # Whether a planned single is hit by its double and triple too.
    any_ring: bool = True


def plan_blocks(fields: Sequence[Field], length: PersonalLength) -> tuple[PlanBlock, ...]:
    """One block per field, then a mixed one over all of them; every block a whole
    number of visits."""
    if not fields:
        return ()
    if len(fields) == 1:
        return (PlanBlock((fields[0],), int(length)),)
    mixed = round(length * MIXED_SHARE / _VISIT) * _VISIT
    each = (length - mixed) // (len(fields) * _VISIT) * _VISIT
    own = tuple(PlanBlock((target,), each) for target in fields)
    return (*own, PlanBlock(tuple(fields), length - each * len(fields)))


@dataclass
class BlockTally:
    darts: int = 0
    hits: int = 0


@dataclass
class PersonalPlayer:
    # The block under way; the number of blocks once the plan is through.
    block: int = 0
    # The field the next dart goes at; None once the plan is through.
    target: Field | None = None
    # Darts the block under way still takes.
    left: int = 0
    darts: int = 0
    hits: int = 0
    blocks: list[BlockTally] = field(default_factory=list)
    # Today's darts and hits per planned field, mixed block included.
    fields: dict[Field, BlockTally] = field(default_factory=dict)


@dataclass
class PersonalProgress:
    players: dict[int, PersonalPlayer]
    # Hits of each replayed turn, in turn order.
    turn_hits: list[int] = field(default_factory=list)
    # The field each dart of each turn went at; None past the plan.
    turn_targets: list[list[Field | None]] = field(default_factory=list)
    winner_id: int | None = None


def aimed_at(blocks: Sequence[PlanBlock], dart: int) -> tuple[int, Field] | None:
    """The block and field of the player's dart number `dart`, from 0; None past the plan."""
    for index, block in enumerate(blocks):
        if dart < block.darts:
            return index, block.fields[dart % len(block.fields)]
        dart -= block.darts
    return None


def personal_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: PersonalOptions
) -> PersonalProgress:
    """Replay the darts in throwing order against the plan; the first player through it wins."""
    blocks = options.blocks
    progress = PersonalProgress(
        {
            player_id: PersonalPlayer(
                blocks=[BlockTally() for _ in blocks],
                fields={target: BlockTally() for target in _planned(blocks)},
            )
            for player_id in player_ids
        }
    )
    for turn in turns:
        player = progress.players[turn.player_id]
        hits = 0
        aimed: list[Field | None] = []
        for dart in turn.darts:
            at = aimed_at(blocks, player.darts)
            player.darts += 1
            aimed.append(None if at is None else at[1])
            if at is None:
                continue
            block, target = at
            hit = planned_target(target, options.any_ring).hit_by(dart.value, dart.multiplier)
            for tally in (player.blocks[block], player.fields[target]):
                tally.darts += 1
                tally.hits += hit
            hits += hit
        player.hits += hits
        progress.turn_hits.append(hits)
        progress.turn_targets.append(aimed)

    planned = sum(block.darts for block in blocks)
    for player_id, player in progress.players.items():
        at = aimed_at(blocks, player.darts)
        player.block, player.target = (len(blocks), None) if at is None else at
        player.left = sum(block.darts for block in blocks[: player.block + 1]) - player.darts
        player.left = max(player.left, 0)
        if at is None and progress.winner_id is None and player.darts >= planned:
            progress.winner_id = player_id
    return progress


def planned_target(field: Field, any_ring: bool = True) -> Target:
    """A planned field as a target; a single takes every ring of its number when `any_ring`."""
    value, multiplier = field
    return Target(value, None if any_ring and multiplier == 1 else multiplier)


def _planned(blocks: Sequence[PlanBlock]) -> list[Field]:
    return list(dict.fromkeys(target for block in blocks for target in block.fields))
