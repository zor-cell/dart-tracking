from itertools import combinations_with_replacement

import pytest

from app.api.features.game.domain.checkout import checkout_route, setup_route
from tests.unit.darts import dart

SINGLES = list(range(1, 21)) + [25]
DOUBLES = [2 * n for n in range(1, 21)] + [50]
TRIPLES = [3 * n for n in range(1, 21)]
FIELDS = SINGLES + DOUBLES + TRIPLES


def finishable(remaining: int, darts: int, double_out: bool) -> bool:
    """Brute force, independent of the code under test."""
    finishes = DOUBLES if double_out else FIELDS
    return any(
        sum(setup) + last == remaining
        for size in range(darts)
        for setup in combinations_with_replacement(FIELDS, size)
        for last in finishes
    )


def points(route: tuple[str, ...]) -> int:
    return sum(dart(label).points for label in route)


def is_double(label: str) -> bool:
    return label == "50" or label.startswith("D")


@pytest.mark.parametrize("double_out", [True, False])
@pytest.mark.parametrize("darts", [1, 2, 3])
def test_route_exists_exactly_when_the_score_can_be_finished(double_out, darts):
    for remaining in range(0, 182):
        route = checkout_route(remaining, darts, double_out)
        assert (route is not None) == finishable(remaining, darts, double_out), remaining
        if route is None:
            continue
        assert points(route) == remaining
        assert len(route) <= darts
        assert checkout_route(remaining, len(route) - 1, double_out) is None, "not the shortest"
        if double_out:
            assert is_double(route[-1]), route


def test_classic_bogey_numbers_have_no_three_dart_finish():
    bogeys = [r for r in range(2, 171) if checkout_route(r, 3, True) is None]
    assert bogeys == [159, 162, 163, 165, 166, 168, 169]


def test_setup_darts_come_first_highest_value_first():
    assert checkout_route(100, 3, True) == ("T20", "D20")
    assert checkout_route(170, 3, True) == ("T20", "T20", "50")


def test_preferred_double_beats_the_conventional_one_at_equal_dart_count():
    assert checkout_route(52, 3, True) == ("12", "D20")
    assert checkout_route(52, 3, True, (16,)) == ("20", "D16")


def test_single_setup_beats_a_preferred_double():
    assert checkout_route(56, 3, True, (16, 20)) == ("16", "D20")
    assert checkout_route(60, 3, True, (16,)) == ("20", "D20")


def test_double_setup_beats_a_treble_setup():
    assert checkout_route(74, 3, True, (16,)) == ("D17", "D20")


def test_fewer_darts_beat_a_preferred_double():
    assert checkout_route(40, 3, True, (16,)) == ("D20",)


def test_single_out_prefers_the_plain_single():
    assert checkout_route(20, 1, False) == ("20",)


@pytest.mark.parametrize("double_out", [True, False])
def test_setup_leaves_a_two_dart_finish(double_out):
    limit = 170 if double_out else 180
    for remaining in range(2, limit + 1):
        if checkout_route(remaining, 1, double_out) is not None:
            assert setup_route(remaining, 1, double_out) is None
            continue
        setup = setup_route(remaining, 1, double_out)
        if setup is None:
            continue
        assert points(setup.darts) + setup.leave == remaining
        assert setup.leave >= (2 if double_out else 1)
        assert checkout_route(setup.leave, 2, double_out) is not None


def test_no_setup_beyond_finishing_range():
    assert setup_route(171, 1, True) is None
    assert setup_route(181, 1, False) is None
