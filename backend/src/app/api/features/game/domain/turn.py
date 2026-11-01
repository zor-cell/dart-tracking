from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.dart import Dart


@dataclass
class Turn:
    """One visit to the oche: up to three darts thrown by a single player.

    A busted turn keeps its darts for statistics but scores nothing.
    """

    player_id: int
    darts: list[Dart] = field(default_factory=list)
    busted: bool = False
    # When the visit was handed over or won; None while it is open.
    ended_at: datetime | None = field(default=None, compare=False)

    @property
    def points(self) -> int:
        return sum(dart.points for dart in self.darts)
