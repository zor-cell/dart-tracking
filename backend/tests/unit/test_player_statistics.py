import math
from datetime import UTC, datetime, timedelta

import pytest

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_status import (
    GameStatus,
    counts_in_statistics,
    effective_status,
)
from app.api.features.game.domain.turn import Turn
from app.api.features.statistics.domain.player_statistics import PlayerStatistics
from tests.unit.darts import darts


def visit(*labels: str, busted: bool = False) -> Turn:
    return Turn(player_id=0, darts=darts(*labels), busted=busted)


def test_won_leg():
    statistics = PlayerStatistics()
    statistics.add_leg(
        301,
        CheckoutMode.DOUBLE_OUT,
        [
            visit("T20", "T20", "T20"),
            visit("T20", "T20", busted=True),
            visit("T20", "T17", "D5"),
        ],
    )

    assert (statistics.darts, statistics.points) == (8, 301)
    assert statistics.average == pytest.approx(3 * 301 / 8)
    assert statistics.best_visit == 180
    assert (statistics.visits_180, statistics.visits_140_plus) == (1, 1)
    assert (statistics.visits_100_plus, statistics.visits_60_plus) == (2, 2)
    assert (statistics.checkout_attempts, statistics.checkout_hits) == (1, 1)
    assert (statistics.first_nine_darts, statistics.first_nine_points) == (8, 301)
    assert (statistics.legs, statistics.legs_won) == (1, 1)
    assert statistics.fields["T20"] == 6
    assert statistics.highest_finish == 121


def test_located_fields_count_only_darts_with_a_tip():
    statistics = PlayerStatistics()
    located = Dart(value=20, multiplier=3, position=(0.0, 103.0))
    turn = Turn(player_id=0, darts=[located, *darts("T20", "5")])
    statistics.add_leg(501, CheckoutMode.DOUBLE_OUT, [turn])

    assert statistics.fields == {"T20": 2, "5": 1}
    assert statistics.located_fields == {"T20": 1}


def test_favourite_visit_is_the_scoring_visit_thrown_most_often():
    statistics = PlayerStatistics()
    statistics.add_leg(
        501,
        CheckoutMode.DOUBLE_OUT,
        [
            visit("0", "0", "0"),
            visit("0", "0", "0"),
            visit("0", "0", "0"),
            visit("20", "1", "5"),
            visit("T20", "20", "1"),
            visit("20", "5", "1"),
        ],
    )

    assert statistics.favourite_visit == 26


def test_lost_leg_counts_every_dart_at_a_double():
    statistics = PlayerStatistics()
    statistics.add_leg(
        301,
        CheckoutMode.DOUBLE_OUT,
        [
            visit("T20", "T20", "T20"),
            visit("T20", "T7", "0"),
            visit("0", "0", "0"),
            visit("20", "20", busted=True),
        ],
    )

    assert (statistics.checkout_attempts, statistics.checkout_hits) == (6, 0)
    assert statistics.first_nine_darts == 9
    assert statistics.first_nine_points == 180 + 81
    assert statistics.legs_won == 0
    assert statistics.highest_finish == 0


def test_single_out_finishes_on_any_field():
    statistics = PlayerStatistics()
    statistics.add_leg(301, CheckoutMode.SINGLE_OUT, [visit("T20", "T20", "T20"), visit("T20", "T20", "1")])

    assert (statistics.checkout_attempts, statistics.checkout_hits) == (1, 1)
    assert statistics.legs_won == 1


def test_leg_out_of_reach_has_no_checkout_attempt():
    statistics = PlayerStatistics()
    statistics.add_leg(501, CheckoutMode.DOUBLE_OUT, [visit("20", "20", "20")])

    assert statistics.checkout_attempts == 0


def at(value: int, multiplier: int, radius: float, degrees: float) -> Dart:
    """A located dart, `degrees` counter-clockwise from +x."""
    angle = math.radians(degrees)
    return Dart(value, multiplier, (radius * math.cos(angle), radius * math.sin(angle)))


def test_darts_at_a_double_are_measured_from_it():
    statistics = PlayerStatistics()
    for dart in (at(0, 0, 175, 90), at(5, 2, 165, 102), at(20, 1, 150, 90)):
        statistics.add_leg(40, CheckoutMode.DOUBLE_OUT, [Turn(player_id=0, darts=[dart])])
    statistics.add_leg(
        20,
        CheckoutMode.DOUBLE_OUT,
        [Turn(player_id=0, darts=[at(0, 0, 175, -18), at(10, 2, 165, -18)])],
    )

    d20, d10 = statistics.doubles[20], statistics.doubles[10]
    assert (d20.attempts, d20.hits, d20.located) == (3, 0, 3)
    assert (d10.attempts, d10.hits, d10.label) == (2, 1, "D10")
    assert d10.distance == pytest.approx(5)
    assert (d10.located, d10.located_hits) == (2, 1)
    assert sum(d20.cells.values()) == 3
    assert d10.fields == {"0": 1, "D10": 1}
    assert d20.fields == {"0": 1, "D5": 1, "20": 1}
    assert statistics.double_darts_located == 5
    assert statistics.double_distance == pytest.approx((d20.distance + 5 + 0) / 5)


def test_single_out_measures_no_double():
    statistics = PlayerStatistics()
    statistics.add_leg(40, CheckoutMode.SINGLE_OUT, [Turn(player_id=0, darts=[at(0, 0, 175, 90)])])

    assert statistics.doubles == {}


def test_scoring_visits_measure_the_grouping():
    statistics = PlayerStatistics()
    statistics.add_leg(
        501,
        CheckoutMode.DOUBLE_OUT,
        [
            Turn(
                player_id=0,
                darts=[Dart(20, 3, (0, 100)), Dart(20, 1, (10, 100)), Dart(1, 1, (-10, 100))],
            ),
            Turn(player_id=0, darts=[Dart(20, 3), Dart(20, 3), Dart(20, 3)]),
            visit("T20", "T20", "T20"),
            visit("0", "0", "0"),
        ],
    )

    assert statistics.grouping == pytest.approx(40 / 3)
    assert (statistics.grouping_darts, statistics.grouping_pairs) == (3, 3)
    assert statistics.scoring_darts == 9
    scatter = statistics.scatter
    assert (scatter.major, scatter.minor, scatter.angle) == pytest.approx((10, 0, 0))
    assert statistics.dart_averages == pytest.approx([60, 140 / 3, 121 / 3])


def test_two_located_darts_count_as_one_pair():
    statistics = PlayerStatistics()
    statistics.add_leg(
        501,
        CheckoutMode.DOUBLE_OUT,
        [Turn(player_id=0, darts=[Dart(20, 3, (0, 100)), Dart(20, 1, (0, 130)), Dart(20, 1)])],
    )

    assert statistics.grouping == pytest.approx(30)
    assert (statistics.grouping_darts, statistics.grouping_pairs) == (2, 1)


def test_no_located_scoring_visit_has_no_grouping():
    statistics = PlayerStatistics()
    statistics.add_leg(501, CheckoutMode.DOUBLE_OUT, [visit("T20", "T20", "T20")])

    assert (statistics.grouping, statistics.scatter) == (None, None)


NOW = datetime.now(UTC)


@pytest.mark.parametrize(
    ("status", "updated_at", "effective"),
    [
        (GameStatus.ACTIVE, NOW, GameStatus.ACTIVE),
        (GameStatus.ACTIVE, NOW - timedelta(hours=25), GameStatus.ABANDONED),
        (GameStatus.FINISHED, NOW - timedelta(days=9), GameStatus.FINISHED),
        (GameStatus.DISCARDED, NOW - timedelta(days=9), GameStatus.DISCARDED),
    ],
)
def test_untouched_open_games_turn_abandoned(status, updated_at, effective):
    assert effective_status(status, updated_at) is effective


@pytest.mark.parametrize(
    ("status", "own_darts", "counts"),
    [
        (GameStatus.FINISHED, 1, True),
        (GameStatus.ABANDONED, 9, True),
        (GameStatus.ABANDONED, 8, False),
        (GameStatus.ACTIVE, 99, False),
        (GameStatus.DISCARDED, 99, False),
    ],
)
def test_which_games_count(status, own_darts, counts):
    assert counts_in_statistics(status, own_darts) is counts
