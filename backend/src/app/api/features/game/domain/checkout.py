"""Checkout route suggestion for x01.

Given the points a player has left and how many darts still remain in the current
turn, find a short dart sequence that finishes the leg. Under double-out the
final dart must land in a double (the bullseye counts as the double bull); under
single-out any field finishes. Returns None when no finish fits into the
available darts — precisely the "no checkout" case the UI must leave blank.

Among the valid routes the search prefers, in order: fewer darts, a more
conventional finishing double, then concentrating the setup into high-value darts
(so 100 comes back as "T20 D20", not "20 20 D20"). It is a suggestion aid, not a
claim to reproduce any specific professional checkout table.
"""

from functools import lru_cache
from itertools import combinations_with_replacement

# A single throwable field: its short label and the points it scores.
Field = tuple[str, int]

_SINGLES: list[Field] = [(str(n), n) for n in range(20, 0, -1)] + [("25", 25)]
_DOUBLES: list[Field] = [(f"D{n}", 2 * n) for n in range(1, 21)] + [("50", 50)]
_TRIPLES: list[Field] = [(f"T{n}", 3 * n) for n in range(1, 21)]

_ALL_FIELDS: list[Field] = _SINGLES + _DOUBLES + _TRIPLES

# Doubles by sector, 25 being the bullseye (double bull), a last-resort finish.
_DOUBLE_PREFERENCE = [20, 16, 8, 4, 2, 18, 10, 12, 14, 6, 19, 17, 15, 13, 11, 9, 7, 5, 3, 1, 25]


@lru_cache(maxsize=None)
def _double_out_rank(preferred: tuple[int, ...]) -> dict[str, int]:
    """Rank of each finishing double: the player's preferred ones first, in their
    order, then the conventional order."""
    order = [*preferred, *(n for n in _DOUBLE_PREFERENCE if n not in preferred)]
    return {("50" if n == 25 else f"D{n}"): rank for rank, n in enumerate(order)}


def _single_out_rank(label: str) -> int:
    """Preference for a single-out finishing dart: land on the plain single when
    the leftover allows it, then a triple, then bull, then a double — so 20 comes
    back as "20" rather than "D10"."""
    if label.startswith("T"):
        return 1
    if label == "50":
        return 2  # the bullseye (double bull)
    if label.startswith("D"):
        return 3
    return 0  # a plain single (or the outer bull "25")


@lru_cache(maxsize=None)
def checkout_route(
    remaining: int, darts: int, double_out: bool, preferred: tuple[int, ...] = ()
) -> tuple[str, ...] | None:
    """A dart sequence finishing `remaining` points within `darts` darts, or None.
    `preferred` lists the doubles (by sector, 25 for bull) to finish on first.

    The returned labels are ordered as thrown: setup darts (highest value first)
    then the finishing dart.
    """
    if remaining <= 0 or darts <= 0:
        return None

    finishes = _DOUBLES if double_out else _ALL_FIELDS
    double_rank = _double_out_rank(preferred)
    rank = (lambda label: double_rank[label]) if double_out else _single_out_rank

    best_cost: tuple[int, int, int] | None = None
    best_route: tuple[str, ...] | None = None

    # Every route uses 0..darts-1 setup darts plus one finishing dart. Setup order
    # does not affect the score, so combinations (not permutations) suffice.
    for setup_size in range(darts):
        for setup in combinations_with_replacement(_ALL_FIELDS, setup_size):
            setup_sum = sum(value for _, value in setup)
            if setup_sum >= remaining:
                continue  # the finishing dart must still score something
            for finish_label, finish_value in finishes:
                if setup_sum + finish_value != remaining:
                    continue
                cost = (
                    setup_size + 1,
                    rank(finish_label),
                    -sum(value * value for _, value in setup),
                )
                if best_cost is None or cost < best_cost:
                    ordered = sorted(setup, key=lambda field: field[1], reverse=True)
                    best_cost = cost
                    best_route = tuple(label for label, _ in ordered) + (finish_label,)

    return best_route
