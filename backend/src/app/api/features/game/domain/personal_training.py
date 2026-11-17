"""Personal training: a fixed plan of blocks at the account's weakest fields, each a
set number of darts or a share of the minutes; done once the plan or its time is through."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.target import Target
from app.api.features.game.domain.training import Field, TrainingLength, TrainingMinutes, first_dart
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


# The plan's darts come in the same lengths as a free training's.
PersonalLength = TrainingLength


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
    located: int = 0
    distance: float = 0.0  # summed mm of the located darts from the field


@dataclass(frozen=True)
class PersonalOptions:
    focus: PersonalFocus = PersonalFocus.ALL
    length: PersonalLength = PersonalLength.MEDIUM
    blocks: tuple[PlanBlock, ...] = ()
    baselines: tuple[Baseline, ...] = ()
    # Whether a planned single is hit by its double and triple too.
    any_ring: bool = True
    # Minutes from the first dart, shared by the blocks as their darts are; None plays by darts.
    minutes: TrainingMinutes | None = None


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
    located: int = 0
    distance: float = 0.0  # summed mm of the located darts from their field


@dataclass
class PersonalPlayer:
    # The block under way; the number of blocks once the plan is through.
    block: int = 0
    # The field the next dart goes at; None once the plan is through.
    target: Field | None = None
    # Darts the block under way still takes.
    left: int = 0
    # The fields of the darts the visit under way still takes.
    ahead: list[Field] = field(default_factory=list)
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


def block_seconds(blocks: Sequence[PlanBlock], minutes: int) -> list[float]:
    """How long each block of a timed plan runs, its share of the minutes by its darts."""
    total = sum(block.darts for block in blocks)
    return [minutes * 60 * block.darts / total for block in blocks]


def timed_block(blocks: Sequence[PlanBlock], minutes: int, elapsed: float) -> int:
    """The block a timed plan is in `elapsed` seconds after its first dart; the last once over."""
    for index, seconds in enumerate(block_seconds(blocks, minutes)):
        if elapsed < seconds:
            return index
        elapsed -= seconds
    return len(blocks) - 1


def personal_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: PersonalOptions
) -> PersonalProgress:
    """Replay the darts in throwing order against the plan; the first player through it wins."""
    if options.minutes is not None and options.blocks:
        return _timed_progress(player_ids, turns, options, options.minutes)
    blocks = options.blocks
    progress = _empty_progress(player_ids, blocks)
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
            hits += _book(player, block, target, dart, options.any_ring)
        player.hits += hits
        progress.turn_hits.append(hits)
        progress.turn_targets.append(aimed)

    planned = sum(block.darts for block in blocks)
    for player_id, player in progress.players.items():
        rest = _visit_rest(turns, player_id)
        through = player.darts >= planned
        # A full visit keeps its block and field on show until it is handed over.
        at = None if through else aimed_at(blocks, player.darts - 1 if rest == 0 else player.darts)
        player.block, player.target = (len(blocks), None) if at is None else at
        player.left = sum(block.darts for block in blocks[: player.block + 1]) - player.darts
        player.left = max(player.left, 0)
        ahead = (aimed_at(blocks, player.darts + index) for index in range(rest))
        player.ahead = [next_at[1] for next_at in ahead if next_at is not None]
        if through and progress.winner_id is None:
            progress.winner_id = player_id
    return progress


def _timed_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: PersonalOptions, minutes: int
) -> PersonalProgress:
    """Replay a timed plan: each visit goes at the block its start falls in, and the
    block's fields take turns dart by dart."""
    blocks = options.blocks
    progress = _empty_progress(player_ids, blocks)
    counts = {player_id: [0] * len(blocks) for player_id in player_ids}
    start = first_dart(turns)
    upcoming = dict.fromkeys(player_ids, 0)
    for index, turn in enumerate(turns):
        player = progress.players[turn.player_id]
        block = _visit_block(turns, index, start, blocks, minutes)
        upcoming[turn.player_id] = block
        hits = 0
        aimed: list[Field | None] = []
        for dart in turn.darts:
            fields = blocks[block].fields
            target = fields[counts[turn.player_id][block] % len(fields)]
            counts[turn.player_id][block] += 1
            player.darts += 1
            aimed.append(target)
            hits += _book(player, block, target, dart, options.any_ring)
        player.hits += hits
        progress.turn_hits.append(hits)
        progress.turn_targets.append(aimed)

    for player_id, player in progress.players.items():
        player.block = upcoming[player_id]
        fields = blocks[player.block].fields
        done = counts[player_id][player.block]
        rest = _visit_rest(turns, player_id)
        player.target = fields[(done - 1 if rest == 0 else done) % len(fields)]
        player.ahead = [fields[(done + index) % len(fields)] for index in range(rest)]
    return progress


def _visit_block(
    turns: Sequence[Turn],
    index: int,
    start: datetime | None,
    blocks: Sequence[PlanBlock],
    minutes: int,
) -> int:
    """The block of visit `index`: where the hand-over before it falls, the first dart's
    time standing in for a hand-over not dated."""
    if index == 0 or start is None:
        return 0
    began = turns[index - 1].ended_at or next(
        (dart.thrown_at for dart in turns[index].darts if dart.thrown_at), None
    )
    if began is None:
        return 0
    return timed_block(blocks, minutes, (began - start).total_seconds())


def _visit_rest(turns: Sequence[Turn], player_id: int) -> int:
    """Darts the player's open visit still takes; a whole visit for a player not at the oche."""
    current = turns[-1] if turns and turns[-1].ended_at is None else None
    thrown = len(current.darts) if current is not None and current.player_id == player_id else 0
    return max(_VISIT - thrown, 0)


def _book(player: PersonalPlayer, block: int, target: Field, dart: Dart, any_ring: bool) -> bool:
    """Counts a dart into its block and field; whether it hit."""
    aimed = planned_target(target, any_ring)
    hit = aimed.hit_by(dart.value, dart.multiplier)
    for tally in (player.blocks[block], player.fields[target]):
        tally.darts += 1
        tally.hits += hit
        if dart.position is not None:
            tally.located += 1
            tally.distance += aimed.distance(*dart.position)
    return hit


def _empty_progress(player_ids: Sequence[int], blocks: Sequence[PlanBlock]) -> PersonalProgress:
    return PersonalProgress(
        {
            player_id: PersonalPlayer(
                blocks=[BlockTally() for _ in blocks],
                fields={target: BlockTally() for target in _planned(blocks)},
            )
            for player_id in player_ids
        }
    )


def planned_target(field: Field, any_ring: bool = True) -> Target:
    """A planned field as a target; a single takes every ring of its number when `any_ring`."""
    value, multiplier = field
    return Target(value, None if any_ring and multiplier == 1 else multiplier)


def _planned(blocks: Sequence[PlanBlock]) -> list[Field]:
    return list(dict.fromkeys(target for block in blocks for target in block.fields))
