from datetime import UTC, datetime, timedelta
from enum import StrEnum


class GameStatus(StrEnum):
    """Whether a game counts. Only games that were actually played belong in the
    statistics; a test run of three darts must not move an average.
    """

    ACTIVE = "active"
    FINISHED = "finished"
    ABANDONED = "abandoned"
    # Not stored on the game: the reading account hid it from its own list.
    DISCARDED = "discarded"


# An open game nobody has touched for this long is over, whatever it says.
ABANDON_AFTER = timedelta(hours=24)

# How long a won game is still reopened on a device that left it open.
RESUME_FINISHED_FOR = timedelta(minutes=15)

# Below this, an abandoned game is a calibration test rather than a session, and
# the history hides it unless asked for abandoned games.
MIN_ABANDONED_DARTS = 9


def effective_status(status: GameStatus, updated_at: datetime) -> GameStatus:
    """`abandoned` is not written anywhere; it is what an untouched open game
    turns into. Deriving it on read keeps it correct without a background job."""
    if status is not GameStatus.ACTIVE:
        return status
    stale = datetime.now(UTC) - updated_at > ABANDON_AFTER
    return GameStatus.ABANDONED if stale else status


def is_resumable(finished: bool, updated_at: datetime | None) -> bool:
    """Whether a device that left the game open should still be put back into it."""
    if updated_at is None:
        return True
    window = RESUME_FINISHED_FOR if finished else ABANDON_AFTER
    return datetime.now(UTC) - updated_at <= window


def counts_in_statistics(status: GameStatus) -> bool:
    """Whether a game may move an average: only once it is won, since an open or
    abandoned one can still be taken up again."""
    return status is GameStatus.FINISHED
