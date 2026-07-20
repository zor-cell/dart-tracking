from dataclasses import dataclass, field


@dataclass
class Turn:
    """One visit to the oche: up to three darts thrown by a single player.

    A busted turn keeps its darts for statistics but scores nothing.
    """

    player_id: int
    darts: list[int] = field(default_factory=list)
    busted: bool = False
