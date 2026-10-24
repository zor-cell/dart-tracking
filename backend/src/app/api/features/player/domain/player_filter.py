"""Which entries an address-book page holds. Every field narrows it; None leaves it open."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerFilter:
    # Part of the name, ignoring case.
    query: str | None = None
    # Linked to another account or not; either way the own entry is left out.
    linked: bool | None = None
