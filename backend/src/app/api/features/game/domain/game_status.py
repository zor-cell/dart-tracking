from datetime import UTC, datetime, timedelta
from enum import StrEnum


class GameStatus(StrEnum):
    """Whether a game counts. Only games that were actually played belong in the
    statistics; a test run of three darts must not move an average.
    """

    ACTIVE = "active"
    FINISHED = "finished"
    ABANDONED = "abandoned"
    DISCARDED = "discarded"


# An open game nobody has touched for this long is over, whatever it says.
ABANDON_AFTER = timedelta(hours=24)

# Below this, an abandoned game is a calibration test rather than a session:
# three visits is the shortest thing that still says something about scoring.
MIN_ABANDONED_DARTS = 9


def effective_status(status: GameStatus, updated_at: datetime) -> GameStatus:
    """`abandoned` is not written anywhere; it is what an untouched open game
    turns into. Deriving it on read keeps it correct without a background job."""
    if status is not GameStatus.ACTIVE:
        return status
    stale = datetime.now(UTC) - updated_at > ABANDON_AFTER
    return GameStatus.ABANDONED if stale else status


def counts_in_statistics(status: GameStatus, own_darts: int) -> bool:
    """Whether a game may move an average. A finished one always does; an
    abandoned one only once it holds more than a test throw (§4.5)."""
    if status is GameStatus.FINISHED:
        return True
    return status is GameStatus.ABANDONED and own_darts >= MIN_ABANDONED_DARTS
