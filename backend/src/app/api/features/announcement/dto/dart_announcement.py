from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game


class DartAnnouncementDto(CamelModel):
    """Server -> announcer: a dart just booked, tracked or entered by hand, for
    the client to phrase.

    `visit_points` is set once the visit is full, busted or won.
    """

    type: Literal["dart_announcement"] = "dart_announcement"
    value: int
    multiplier: int
    visit_points: int | None
    busted: bool
    won: bool

    @classmethod
    def from_entity(cls, dart: Dart, game: Game) -> Self:
        turn = game.current_turn
        won = game.winner is not None
        visit_over = won or game.darts_remaining == 0
        return cls(
            value=dart.value,
            multiplier=dart.multiplier,
            visit_points=turn.points if visit_over else None,
            busted=turn.busted,
            won=won,
        )
