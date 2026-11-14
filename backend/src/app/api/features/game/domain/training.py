"""Free training: throw for as long as you like, at nothing, at a random field or
at fields of your own; nobody wins, the game is ended by hand."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from random import Random

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.turn import Turn

# A board field as value and multiplier: (19, 3) is T19, (25, 2) the bull.
type Field = tuple[int, int]

# Most hits a field may ask for before the target moves on.
MAX_REPEATS = 9


class TrainingGoal(StrEnum):
    """FREE: no target. RANDOM: a random field. FIELDS: the chosen fields. A target
    stays until it was hit often enough."""

    FREE = "free"
    RANDOM = "random"
    FIELDS = "fields"


class TrainingRing(StrEnum):
    """Which fields a random target is drawn from; the bull has no triple."""

    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    MIXED = "mixed"


@dataclass(frozen=True)
class TrainingOptions:
    goal: TrainingGoal = TrainingGoal.FREE
    ring: TrainingRing = TrainingRing.SINGLE
    fields: tuple[Field, ...] = ()
    # Hits a target takes before the next one comes up.
    repeats: int = 1
    # Whether the own fields come up at random rather than in order.
    shuffle: bool = False
    # What the random targets are drawn from, so a replay names the same ones.
    seed: int = 0


@dataclass
class FieldTally:
    darts: int = 0
    hits: int = 0


@dataclass
class TrainingPlayer:
    # The field the next dart goes at; None without a target.
    target: Field | None = None
    # Hits the target still takes before the next one comes up.
    left: int = 0
    darts: int = 0
    hits: int = 0
    # Darts and hits per target, in the order the targets first came up.
    tallies: dict[Field, FieldTally] = field(default_factory=dict)


@dataclass
class TrainingProgress:
    players: dict[int, TrainingPlayer]
    # Hits of each replayed turn, in turn order.
    turn_hits: list[int] = field(default_factory=list)
    # The field each dart of each turn went at; None without a target.
    turn_targets: list[list[Field | None]] = field(default_factory=list)
    winner_id: int | None = None


def random_fields(ring: TrainingRing) -> list[Field]:
    """Every field a random target of `ring` may name."""
    rings = {
        TrainingRing.SINGLE: (1,),
        TrainingRing.DOUBLE: (2,),
        TrainingRing.TRIPLE: (3,),
        TrainingRing.MIXED: (1, 2, 3),
    }[ring]
    numbers = [(value, multiplier) for multiplier in rings for value in range(1, 21)]
    return numbers + [(25, multiplier) for multiplier in rings if multiplier < 3]


class _Targets:
    """One player's targets: the fields in order, or drawn at random and never
    the same twice running."""

    def __init__(self, fields: Sequence[Field], random: Random | None) -> None:
        self._fields = fields
        self._random = random
        self._index = 0 if random is None else random.randrange(len(fields))

    @property
    def current(self) -> Field:
        return self._fields[self._index]

    def advance(self) -> None:
        count = len(self._fields)
        if self._random is None or count == 1:
            self._index = (self._index + 1) % count
        else:
            self._index = (self._index + self._random.randrange(1, count)) % count


def _targets(options: TrainingOptions, player_id: int) -> _Targets | None:
    random = Random(f"{options.seed}:{player_id}")
    if options.goal is TrainingGoal.RANDOM:
        return _Targets(random_fields(options.ring), random)
    if options.goal is TrainingGoal.FIELDS and options.fields:
        return _Targets(options.fields, random if options.shuffle else None)
    return None


def training_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: TrainingOptions
) -> TrainingProgress:
    """Replay the darts in throwing order against the target each one went at."""
    progress = TrainingProgress({player_id: TrainingPlayer() for player_id in player_ids})
    targets = {player_id: _targets(options, player_id) for player_id in player_ids}
    for player_id, own in targets.items():
        if own is not None:
            progress.players[player_id].target = own.current
            progress.players[player_id].left = options.repeats

    for turn in turns:
        player = progress.players[turn.player_id]
        own = targets[turn.player_id]
        hits = 0
        aimed: list[Field | None] = []
        for dart in turn.darts:
            player.darts += 1
            aimed.append(player.target)
            if own is None or player.target is None:
                continue
            tally = player.tallies.setdefault(player.target, FieldTally())
            tally.darts += 1
            if not _hits(dart, player.target):
                continue
            tally.hits += 1
            hits += 1
            player.left -= 1
            if player.left == 0:
                own.advance()
                player.target = own.current
                player.left = options.repeats
        player.hits += hits
        progress.turn_hits.append(hits)
        progress.turn_targets.append(aimed)
    return progress


def _hits(dart: Dart, target: Field) -> bool:
    return (dart.value, dart.multiplier) == target
