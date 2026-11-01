from enum import StrEnum


class PlayerCount(StrEnum):
    """How many seats a game has, as the history and the statistics narrow it."""

    SOLO = "solo"
    DUEL = "duel"
    GROUP = "group"

    @property
    def bounds(self) -> tuple[int, int | None]:
        """The fewest and most seats, both inclusive; None for no upper bound."""
        match self:
            case PlayerCount.SOLO:
                return 1, 1
            case PlayerCount.DUEL:
                return 2, 2
            case PlayerCount.GROUP:
                return 3, None
