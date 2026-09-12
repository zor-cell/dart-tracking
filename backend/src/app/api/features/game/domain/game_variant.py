from enum import StrEnum


class GameVariant(StrEnum):
    """Which direction the score runs: x01 counts down from the mode to zero,
    elimination counts up to it and resets whoever is on the score just hit
    (docs/feature/spielmodi.md)."""

    X01 = "x01"
    ELIMINATION = "elimination"
