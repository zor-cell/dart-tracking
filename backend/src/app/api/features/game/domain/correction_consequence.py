from dataclasses import dataclass


@dataclass(frozen=True)
class CorrectionConsequence:
    """What a correction in a closed visit changes beyond it; booked only once confirmed."""

    # The visit that now wins the game, and its winner, although later ones were
    # thrown; those are dropped.
    won_at: int | None = None
    winner_id: int | None = None
    # Players now out or placed before visits they threw; those count nothing.
    out: tuple[int, ...] = ()
