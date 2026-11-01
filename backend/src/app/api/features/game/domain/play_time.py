"""How long a game was actually played."""

from datetime import datetime, timedelta

from app.api.features.game.domain.game import Game

# A longer gap between two darts or handovers is a break, not play.
PAUSE = timedelta(minutes=10)


def play_time(game: Game, started_at: datetime) -> timedelta | None:
    """The gaps from the start through every dart and handover, breaks left out;
    None without darts, or when one has no time, as in games from before times were kept."""
    moments = [started_at]
    for turn in game.turns:
        if any(dart.thrown_at is None for dart in turn.darts):
            return None
        moments += [dart.thrown_at for dart in turn.darts if dart.thrown_at is not None]
        if turn.ended_at is not None:
            moments.append(turn.ended_at)
    if len(moments) == 1:
        return None
    moments.sort()
    gaps = (later - earlier for earlier, later in zip(moments, moments[1:]))
    return sum((gap for gap in gaps if gap <= PAUSE), timedelta())
