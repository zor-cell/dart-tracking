"""What the announcer calls out, before it is worded in a language."""

from dataclasses import dataclass
from typing import Self

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.cricket import CricketHit, CricketOptions, cricket_hit
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.personal_training import PersonalProgress
from app.api.features.game.domain.training import TrainingProgress


@dataclass(frozen=True)
class DartCall:
    """A dart just booked. `visit_points` is set once the visit is full, busted or won;
    `eliminated` names whoever it sent back to zero; `cricket` is what it did to its
    Cricket number; `target` the training field it moved on to while darts are left."""

    value: int
    multiplier: int
    visit_points: int | None
    busted: bool
    won: bool
    eliminated: tuple[str, ...]
    cricket: CricketHit | None = None
    target: tuple[int, int] | None = None

    @classmethod
    def of(cls, dart: Dart, game: Game, eliminated: set[int], index: int = -1) -> Self:
        """The dart at `index` of the open visit; points are called in the points variants only."""
        turn = game.current_turn
        hit = None
        if isinstance(game.options, CricketOptions) and turn.darts:
            ids = [player.id for player in game.players]
            hit = cricket_hit(ids, game.turns, game.options, index)
        won = game.winner is not None
        visit_over = won or game.darts_remaining == 0
        return cls(
            value=dart.value,
            multiplier=dart.multiplier,
            visit_points=turn.points if visit_over and game.variant.counts_points else None,
            busted=turn.busted,
            won=won,
            eliminated=tuple(p.name for p in game.players if p.id in eliminated),
            cricket=hit,
            target=None if visit_over else _moved_target(game, index),
        )


def _moved_target(game: Game, index: int) -> tuple[int, int] | None:
    """The training field the last dart of the open visit moved on to, if it did."""
    progress, darts = game.progress, game.current_turn.darts
    if not isinstance(progress, TrainingProgress | PersonalProgress) or not darts:
        return None
    if index not in (-1, len(darts) - 1):
        return None
    target = progress.players[game.current_player.id].target
    return target if target != progress.turn_targets[-1][-1] else None


@dataclass(frozen=True)
class TurnCall:
    """The next visit is ready for `player`; `score` is what the scoreboard shows
    them, None outside the points variants. `target` is the field to hit next in
    Around the Clock and the trainings, as value and multiplier."""

    player: str
    score: int | None
    target: tuple[int, int] | None = None

    @classmethod
    def of(cls, game: Game) -> Self:
        player = game.current_player
        if isinstance(game.options, ClockOptions) and game.progress is not None:
            value = game.progress.players[player.id].target
            zone = game.options.zone
            ring = 1 if zone is ClockZone.ANY else 2 if value == 25 or zone is ClockZone.DOUBLE else 3
            return cls(player.name, None, None if value is None else (value, ring))
        if isinstance(progress := game.progress, TrainingProgress | PersonalProgress):
            return cls(player.name, None, progress.players[player.id].target)
        if not game.variant.counts_points or game.mode is None:
            return cls(player=player.name, score=None)
        remaining = game.remaining(player.id)
        return cls(
            player=player.name,
            score=remaining if game.variant is GameVariant.X01 else game.mode - remaining,
        )
