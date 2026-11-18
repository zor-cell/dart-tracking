from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.api.features.game.domain.cricket import (
    CRICKET_TARGETS,
    CricketOptions,
    CricketScoring,
    cricket_throws,
)
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.statistics.domain.cricket_statistics import CricketStatistics
from tests.unit.darts import dart, new_game, play

PLAYED_AT = datetime(2026, 11, 1, tzinfo=UTC)
S20 = (0.0, 60.0)
S3 = (0.0, -60.0)


def cricket(players=2, scoring=CricketScoring.STANDARD):
    return new_game(players, variant=GameVariant.CRICKET, options=CricketOptions(scoring))


def located(game, turn, index, position):
    """Puts the dart at `index` of turn `turn` at board mm `position`."""
    darts = game.turns[turn].darts
    darts[index] = replace(darts[index], position=position)


def tally(game, seat=0):
    statistics = CricketStatistics()
    statistics.add_game(game, seat, PLAYED_AT)
    return statistics


def test_each_throw_knows_its_marks_and_the_numbers_still_open():
    game = cricket(scoring=CricketScoring.NO_SCORE)
    play(game, "T20 20 19", "0")

    throws = list(cricket_throws([0, 1], game.turns, game.options))

    assert [throw.marks for throw in throws] == [3, 0, 1, 0]
    assert throws[0].open == frozenset(CRICKET_TARGETS)
    assert 20 not in throws[1].open
    assert throws[3].player_id == 1 and 20 in throws[3].open


def test_a_closed_number_stays_open_while_an_opponent_can_still_be_scored_on():
    game = cricket()
    play(game, "T20 20")

    second = list(cricket_throws([0, 1], game.turns, game.options))[1]

    assert 20 in second.open and second.marks == 1


def test_the_throws_stop_at_the_win():
    game = cricket(players=1)
    play(game, "T20 T19 T18", "T17 T16 T15", "50 25 T20")

    assert len(list(cricket_throws([0], game.turns, game.options))) == 8


def test_marks_per_round_count_three_darts_as_a_round():
    game = cricket()
    play(game, "T20 T19 0", "0 0 0", "20 0 0")

    statistics = tally(game)

    assert (statistics.darts, statistics.marks) == (6, 7)
    assert statistics.mpr == pytest.approx(3.5)
    assert statistics.empty == 3


def test_visits_are_counted_by_their_marks_and_the_best_links_its_visit():
    game = cricket()
    play(game, "20 0 0", "T20 T20 T20", "T19 T18 D17")

    statistics = tally(game)

    assert statistics.visits == {1: 1, 8: 1}
    assert statistics.best_visit == 8
    assert statistics.best_visit_at is not None and statistics.best_visit_at.visit == 2
    assert statistics.favourite_visit == 8


def test_a_dart_on_an_open_number_is_no_distance_away():
    game = cricket()
    play(game, "20 3")
    located(game, 0, 0, S20)
    on_open = tally(game).mean_distance
    located(game, 0, 1, S3)

    statistics = tally(game)

    assert on_open == 0
    assert statistics.games[0].located == 2
    assert statistics.mean_distance is not None and statistics.mean_distance > 0
    assert sum(statistics.hits.located_fields.values()) == 2


def test_a_closed_number_is_measured_to_the_nearest_one_still_open():
    game = cricket(scoring=CricketScoring.NO_SCORE)
    play(game, "T20 20")
    located(game, 0, 1, S20)

    statistics = tally(game)

    assert statistics.games[0].located == 1
    assert statistics.mean_distance is not None and statistics.mean_distance > 0
    assert statistics.empty == 1


def test_wins_count_only_against_an_opponent():
    solo = cricket(players=1)
    play(solo, "T20 T19 T18", "T17 T16 T15", "50 25")
    duel = cricket()
    play(duel, "0", "T20")
    duel.turns[-1].darts.append(dart("0"))

    statistics = CricketStatistics()
    statistics.add_game(solo, 0, PLAYED_AT)
    statistics.add_game(duel, 0, PLAYED_AT)

    assert (statistics.games_with_opponent, statistics.wins) == (1, 0)
    assert statistics.games[0].won
