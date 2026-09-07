"""Pairs up what the tracker claimed with what the players accepted.

Counting corrections overstates the error: one missed dart shifts the whole
visit and costs several undos (docs/feature/auswertung.md §3).
"""

from collections.abc import Sequence
from enum import StrEnum

# A shifted sequence has to read as one missed and one spurious dart rather than
# as two mis-scored ones, so a substitution costs exactly as much as that pair.
# On a tie the diagonal wins, which keeps a plain mis-score a substitution.
_SUBSTITUTION_COST = 2
_GAP_COST = 1


class DartOutcome(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"  # booked, but as the wrong field
    MISSED = "missed"  # thrown, never booked by the camera
    PHANTOM = "phantom"  # booked without a dart behind it


def align(
    tracked: Sequence[str], expected: Sequence[str]
) -> list[tuple[int | None, int | None]]:
    """Cheapest pairing of the two label sequences, in throw order.

    Each pair is `(index into tracked, index into expected)`; `None` on a side
    is a gap — a dart the camera never booked, or one it booked alone.
    """
    rows, columns = len(tracked), len(expected)
    cost = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(1, rows + 1):
        cost[row][0] = row * _GAP_COST
    for column in range(1, columns + 1):
        cost[0][column] = column * _GAP_COST

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            step = 0 if tracked[row - 1] == expected[column - 1] else _SUBSTITUTION_COST
            cost[row][column] = min(
                cost[row - 1][column - 1] + step,
                cost[row - 1][column] + _GAP_COST,
                cost[row][column - 1] + _GAP_COST,
            )

    pairs: list[tuple[int | None, int | None]] = []
    row, column = rows, columns
    while row > 0 or column > 0:
        if row > 0 and column > 0:
            step = 0 if tracked[row - 1] == expected[column - 1] else _SUBSTITUTION_COST
            if cost[row][column] == cost[row - 1][column - 1] + step:
                pairs.append((row - 1, column - 1))
                row -= 1
                column -= 1
                continue
        if row > 0 and cost[row][column] == cost[row - 1][column] + _GAP_COST:
            pairs.append((row - 1, None))
            row -= 1
            continue
        pairs.append((None, column - 1))
        column -= 1

    pairs.reverse()
    return pairs


def outcome_of(tracked_label: str | None, expected_label: str | None) -> DartOutcome:
    """What one aligned pair says about the tracker."""
    if tracked_label is None:
        return DartOutcome.MISSED
    if expected_label is None:
        return DartOutcome.PHANTOM
    return DartOutcome.CORRECT if tracked_label == expected_label else DartOutcome.WRONG
