"""Around the Clock: hit 1 to 20 in order, then the bull; the first through wins."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

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
    player_ids: Sequence[int], turns: Sequence[Turn], options: ClockOptions
) -> ClockProgress:
    """Replay the darts in throwing order until the first player is through."""
    progress = ClockProgress({player_id: ClockPlayer() for player_id in player_ids})
    bull = len(CLOCK_TARGETS) - 1
    for turn in turns:
        player = progress.players[turn.player_id]
        start = player.position
        for dart in turn.darts:
            if progress.winner_id is not None:
                break
            player.darts += 1
            target = player.target
            if target is None or not clock_hit(dart, target, options.zone):
                continue
            player.hits += 1
            steps = dart.multiplier if options.skip and target != 25 else 1
            player.position = len(CLOCK_TARGETS) if target == 25 else min(player.position + steps, bull)
            if player.target is None:
                progress.winner_id = turn.player_id
        progress.turn_steps.append(player.position - start)
    return progress
