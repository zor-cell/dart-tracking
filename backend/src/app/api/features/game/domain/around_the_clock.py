"""Around the Clock: hit 1 to 20 in order, then the bull; the first through wins."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Self

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.turn import Turn

CLOCK_TARGETS = (*range(1, 21), 25)


class ClockZone(StrEnum):
    """Which ring of the target counts. The bull has no triple: DOUBLE and TRIPLE take
    the bullseye there, ANY either bull."""

    ANY = "any"
    DOUBLE = "double"
    TRIPLE = "triple"


@dataclass(frozen=True)
class ClockOptions:
    zone: ClockZone = ClockZone.ANY
    # Whether a double moves on two targets and a triple three, never past the bull.
    skip: bool = False


@dataclass
class ClockPlayer:
    # Index into CLOCK_TARGETS of the next target; its length once through.
    position: int = 0
    hits: int = 0
    darts: int = 0

    @property
    def target(self) -> int | None:
        return CLOCK_TARGETS[self.position] if self.position < len(CLOCK_TARGETS) else None


@dataclass
class ClockProgress:
    players: dict[int, ClockPlayer]
    # Targets each replayed turn moved on, in turn order.
    turn_steps: list[int] = field(default_factory=list)
    winner_id: int | None = None


def clock_hit(dart: Dart, target: int, zone: ClockZone) -> bool:
    if dart.value != target or dart.multiplier == 0:
        return False
    if target == 25:
        return zone is ClockZone.ANY or dart.multiplier == 2
    match zone:
        case ClockZone.ANY:
            return True
        case ClockZone.DOUBLE:
            return dart.multiplier == 2
        case ClockZone.TRIPLE:
            return dart.multiplier == 3


def clock_progress(
    player_ids: Sequence[int],
    turns: Sequence[Turn],
    options: ClockOptions,
    voided: Collection[int] = (),
) -> ClockProgress:
    """Replay the darts in throwing order; a voided turn moves nobody on."""
    progress = ClockProgress({player_id: ClockPlayer() for player_id in player_ids})
    for index, turn in enumerate(turns):
        player = progress.players[turn.player_id]
        if index in voided:
            progress.turn_steps.append(0)
            continue
        progress.turn_steps.append(_advance(player, turn, options))
        if progress.winner_id is None and player.target is None:
            progress.winner_id = turn.player_id
    return progress


def _advance(player: ClockPlayer, turn: Turn, options: ClockOptions) -> int:
    """Book one visit for its thrower; returns the targets it moved on."""
    start = player.position
    bull = len(CLOCK_TARGETS) - 1
    for dart in turn.darts:
        target = player.target
        if target is None:
            break
        player.darts += 1
        if not clock_hit(dart, target, options.zone):
            continue
        player.hits += 1
        steps = dart.multiplier if options.skip and target != 25 else 1
        player.position = len(CLOCK_TARGETS) if target == 25 else min(player.position + steps, bull)
    return player.position - start


@dataclass
class ClockBoard:
    """Where everyone stands on the clock, for replaying the race to the bull."""

    options: ClockOptions
    players: dict[int, ClockPlayer]

    @classmethod
    def start(cls, player_ids: Sequence[int], options: ClockOptions) -> Self:
        return cls(options, {player_id: ClockPlayer() for player_id in player_ids})

    def play(self, turn: Turn) -> None:
        _advance(self.players[turn.player_id], turn, self.options)

    def reached(self, player_id: int) -> bool:
        return self.players[player_id].target is None

    def copy(self) -> Self:
        return replace(self, players={key: replace(player) for key, player in self.players.items()})
