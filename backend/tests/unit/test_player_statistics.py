from datetime import UTC, datetime, timedelta

import pytest

from app.api.features.game.domain.checkout_mode import CheckoutMode
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
    assert (statistics.best_visit, statistics.visits_180, statistics.visits_100_plus) == (180, 1, 2)
    assert (statistics.checkout_attempts, statistics.checkout_hits) == (1, 1)
    assert (statistics.first_nine_darts, statistics.first_nine_points) == (8, 301)
    assert (statistics.legs, statistics.legs_won, statistics.legs_with_chance) == (1, 1, 1)
    assert statistics.fields["T20"] == 6


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
    assert (statistics.legs_won, statistics.legs_with_chance) == (0, 1)


def test_single_out_finishes_on_any_field():
    statistics = PlayerStatistics()
    statistics.add_leg(301, CheckoutMode.SINGLE_OUT, [visit("T20", "T20", "T20"), visit("T20", "T20", "1")])

    assert (statistics.checkout_attempts, statistics.checkout_hits) == (1, 1)
    assert statistics.legs_won == 1


def test_leg_out_of_reach_was_no_chance():
    statistics = PlayerStatistics()
    statistics.add_leg(501, CheckoutMode.DOUBLE_OUT, [visit("20", "20", "20")])

    assert statistics.legs_with_chance == 0
    assert statistics.checkout_attempts == 0


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
