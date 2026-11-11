"""What the announcer calls out, before it is worded in a language."""

from dataclasses import dataclass
from typing import Self

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant


@dataclass(frozen=True)
class DartCall:
    """A dart just booked. `visit_points` is set once the visit is full, busted or
    won; `eliminated` names whoever the dart sent back to zero."""

    value: int
    multiplier: int
    visit_points: int | None
    busted: bool
    won: bool
    eliminated: tuple[str, ...]

    @classmethod
    def of(cls, dart: Dart, game: Game, eliminated: set[int]) -> Self:
        """The visit's points are called in the points variants only."""
        turn = game.current_turn
        won = game.winner is not None
        visit_over = won or game.darts_remaining == 0
        return cls(
            value=dart.value,
            multiplier=dart.multiplier,
            visit_points=turn.points if visit_over and game.variant.counts_points else None,
            busted=turn.busted,
            won=won,
            eliminated=tuple(p.name for p in game.players if p.id in eliminated),
        )


@dataclass(frozen=True)
class TurnCall:
    """The next visit is ready for `player`; `score` is what the scoreboard shows
    them, None outside the points variants."""

    player: str
    score: int | None

    @classmethod
    def of(cls, game: Game) -> Self:
        player = game.current_player
        if not game.variant.counts_points or game.mode is None:
            return cls(player=player.name, score=None)
        remaining = game.remaining(player.id)
        return cls(
            player=player.name,
            score=remaining if game.variant is GameVariant.X01 else game.mode - remaining,
        )
