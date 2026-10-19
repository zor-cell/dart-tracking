from dataclasses import dataclass


@dataclass
class Player:
    """Identity only. The remaining score is derived from the game's turns."""

    id: int
    name: str
    identity_id: str
    # Finishing doubles by sector (25 for bull) the linked account prefers, in order.
    preferred_doubles: tuple[int, ...] = ()
