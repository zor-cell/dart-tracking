from enum import StrEnum


class GameStatus(StrEnum):
    """Whether a game counts. Only games that were actually played belong in the
    statistics; a test run of three darts must not move an average (see
    docs/feature/persistenz.md §4.5).
    """

    ACTIVE = "active"
    FINISHED = "finished"
    ABANDONED = "abandoned"
    DISCARDED = "discarded"
