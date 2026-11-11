"""Killer: every player owns a number. Hitting your own zone makes you a killer; a
killer's hit on another's zone takes a life, on their own zone one of their own."""

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.turn import Turn

KILLER_NUMBERS = tuple(range(1, 21))


class KillerZone(StrEnum):
    """Which part of a number counts. ANY: every ring, a double hitting twice and a
    triple three times."""

    DOUBLE = "double"
    TRIPLE = "triple"
    ANY = "any"


@dataclass(frozen=True)
class KillerOptions:
    # Each seat's number, in seat order.
    numbers: tuple[int, ...]
    lives: int = 3
    zone: KillerZone = KillerZone.DOUBLE


@dataclass
class KillerPlayer:
    number: int
    lives: int
    killer: bool = False
    # Lives this player took from others.
    kills: int = 0
    darts: int = 0

    @property
    def out(self) -> bool:
        return self.lives == 0


@dataclass
class KillerProgress:
    players: dict[int, KillerPlayer]
    # Who each replayed turn knocked out, in turn order.
    knocked_out: list[set[int]] = field(default_factory=list)
    winner_id: int | None = None


def deal_numbers(players: int) -> tuple[int, ...]:
    """A different number for every seat, drawn at random."""
    return tuple(random.sample(KILLER_NUMBERS, players))


def zone_hits(dart: Dart, number: int, zone: KillerZone) -> int:
    """How often the dart hits `number` in the zone that counts."""
    if dart.value != number or dart.multiplier == 0:
        return 0
    match zone:
        case KillerZone.DOUBLE:
            return int(dart.multiplier == 2)
        case KillerZone.TRIPLE:
            return int(dart.multiplier == 3)
        case KillerZone.ANY:
            return dart.multiplier


def killer_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: KillerOptions
) -> KillerProgress:
    """Replay the darts in throwing order until one player alone has lives left."""
    progress = KillerProgress(
        {
            player_id: KillerPlayer(number=number, lives=options.lives)
            for player_id, number in zip(player_ids, options.numbers, strict=True)
        }
    )
    for turn in turns:
        knocked: set[int] = set()
        for dart in turn.darts:
            if progress.winner_id is not None:
                break
            knocked |= _throw(progress.players, turn.player_id, dart, options.zone)
            alive = [player_id for player_id, player in progress.players.items() if not player.out]
            if len(alive) == 1 and len(progress.players) > 1:
                progress.winner_id = alive[0]
        progress.knocked_out.append(knocked)
    return progress


def _throw(
    players: dict[int, KillerPlayer], thrower_id: int, dart: Dart, zone: KillerZone
) -> set[int]:
    """Book one dart and return whoever it knocked out."""
    thrower = players[thrower_id]
    thrower.darts += 1
    if thrower.out:
        return set()
    owner_id = next((pid for pid, p in players.items() if p.number == dart.value), None)
    if owner_id is None or (hits := zone_hits(dart, dart.value, zone)) == 0:
        return set()
    owner = players[owner_id]
    if owner_id == thrower_id and not thrower.killer:
        thrower.killer = True
        return set()
    if not thrower.killer or owner.out:
        return set()
    taken = min(hits, owner.lives)
    owner.lives -= taken
    if owner_id != thrower_id:
        thrower.kills += taken
    return {owner_id} if owner.out else set()
