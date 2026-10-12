"""A person one plays with, account or not. Called an identity because the game
feature's `Player` is the seat at the oche — this is who sits in it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerIdentity:
    id: str
    display_name: str
    # Set only where this identity *is* an account — the owner's own entry.
    user_id: str | None = None
