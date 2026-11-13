from enum import StrEnum


class GameVariant(StrEnum):
    """Which game is played. x01 counts down from the mode to zero, elimination counts
    up to it and resets whoever is on the score just hit; the others have own rules."""

    X01 = "x01"
    ELIMINATION = "elimination"
    CRICKET = "cricket"
    KILLER = "killer"
    AROUND_THE_CLOCK = "around_the_clock"

    @property
    def counts_points(self) -> bool:
        """Whether the game runs on a points total between zero and the mode."""
        return self in (GameVariant.X01, GameVariant.ELIMINATION)

    @property
    def races(self) -> bool:
        """Whether everyone runs for the same goal, so places follow the finishing order."""
        return self in (GameVariant.X01, GameVariant.ELIMINATION, GameVariant.AROUND_THE_CLOCK)
