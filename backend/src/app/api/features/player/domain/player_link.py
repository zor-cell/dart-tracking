from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerLink:
    """An entry in someone else's address book that is linked to this account.
    A retired one has left that address book and only holds past games."""

    player_id: str
    owner_name: str
    retired: bool = False
