from dataclasses import dataclass


@dataclass
class Player:
    """Identity only. The remaining score is derived from the game's turns."""

    id: int
    name: str
