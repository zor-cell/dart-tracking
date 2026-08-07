from dataclasses import dataclass, field

from app.api.features.game.entity.dart import Dart


@dataclass
class Turn:
    """One visit to the oche: up to three darts thrown by a single player.

    A busted turn keeps its darts for statistics but scores nothing.
    """

    player_id: int
    darts: list[Dart] = field(default_factory=list)
    busted: bool = False

    @property
    def points(self) -> int:
        return sum(dart.points for dart in self.darts)
