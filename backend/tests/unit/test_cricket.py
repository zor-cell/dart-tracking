import pytest

from app.api.features.game.domain.cricket import CricketOptions, CricketScoring
from app.api.features.game.domain.game_variant import GameVariant
from tests.unit.darts import dart, darts, new_game, play

CLOSE_ALL = ("T20 T19 T18", "T17 T16 T15", "50 25")


def cricket(players=2, scoring=CricketScoring.STANDARD):
    return new_game(players, variant=GameVariant.CRICKET, options=CricketOptions(scoring))


def interleave(own, other="0"):
    """Player 0 throws `own`, everyone else misses in between."""
    return [visit for pair in zip(own, [other] * len(own)) for visit in pair][:-1]


def test_a_cricket_game_keeps_no_points_total():
    game = cricket()

    assert game.mode is None
    assert game.checkout_mode is None
    assert game.checkout is None


@pytest.mark.parametrize(
    ("labels", "marks"),
    [
        ("20", {20: 1}),
        ("D20", {20: 2}),
        ("T20", {20: 3}),
        ("25", {25: 1}),
        ("50", {25: 2}),
        ("50 25", {25: 3}),
        ("14 D10 0", {}),
        ("T15 D16 17", {15: 3, 16: 2, 17: 1}),
    ],
)
def test_singles_doubles_and_triples_are_one_two_and_three_marks(labels, marks):
    game = cricket()
    play(game, labels)

    expected = {target: marks.get(target, 0) for target in (20, 19, 18, 17, 16, 15, 25)}
    assert game.progress.players[0].marks == expected
    assert game.progress.players[0].points == 0


def test_marks_beyond_three_score_while_an_opponent_is_open():
    game = cricket()
    play(game, "D20 T20", "0", "T20 25")

    assert game.progress.players[0].marks[20] == 3
    assert game.progress.players[0].points == 40 + 60


def test_the_bull_scores_25_a_mark():
    game = cricket()
    play(game, "50 50 50")

    assert game.progress.players[0].points == 25 + 50


def test_a_number_both_closed_scores_nothing():
    game = cricket()
    play(game, "T20", "T20", "T20 T20")

    assert game.progress.players[0].points == 0
    assert game.progress.players[1].points == 0


def test_cut_throat_gives_the_points_to_every_opponent_still_open():
    game = cricket(3, CricketScoring.CUT_THROAT)
    play(game, "T20 T20", "T20", "0", "T20")

    progress = game.progress
    assert progress.players[0].points == 0
    assert progress.players[1].points == 60
    assert progress.players[2].points == 120


def test_no_score_books_marks_only():
    game = cricket(scoring=CricketScoring.NO_SCORE)
    play(game, "T20 T20 T20")

    assert game.progress.players[0].points == 0
    assert game.progress.players[0].marks[20] == 3


def test_closing_everything_level_on_points_wins_at_once():
    game = cricket()
    play(game, *interleave(CLOSE_ALL))

    assert game.winner is game.players[0]
    assert game.current_turn.darts == darts("50", "25")
    assert game.darts_remaining == 1
    assert not game.register_dart(dart("20"))
    assert game.shadow_darts == darts("20")


def test_closing_everything_behind_on_points_plays_on_until_level():
    game = cricket()
    play(game, "T20 T19 T18", "T15 T15 T15", "T17 T16 T15", "0", "50 25")

    assert game.winner is None
    assert game.progress.players[1].points == 90

    game.next_player()
    play(game, "0")
    game.next_player()
    play(game, "T20")
    assert game.winner is None
    assert game.progress.players[0].points == 60

    play(game, "T20")
    assert game.winner is game.players[0]
    assert game.progress.players[0].points == 120


def test_cut_throat_needs_the_fewest_points_to_win():
    game = cricket(scoring=CricketScoring.CUT_THROAT)
    play(game, "T15 T15", "T20 T19 T18", "0", "T17 T16 T15", "0", "50 25")

    assert game.progress.players[1].points == 45
    assert game.winner is None

    play(game, "T20")
    assert game.progress.players[0].points == 60
    assert game.winner is game.players[1]


def test_cut_throat_wins_with_fewest_points_once_closed():
    game = cricket(scoring=CricketScoring.CUT_THROAT)
    play(game, *interleave(CLOSE_ALL, "T20 T20"))

    assert game.progress.players[1].points == 0
    assert game.progress.players[0].points == 0
    assert game.winner is game.players[0]


def test_no_score_is_won_by_the_first_to_close_everything():
    game = cricket(scoring=CricketScoring.NO_SCORE)
    play(game, *interleave(CLOSE_ALL, "T20 T20 T20"))

    assert game.winner is game.players[0]


def test_a_single_player_wins_by_closing_everything():
    game = cricket(1)
    for visit in CLOSE_ALL:
        play(game, visit)
        if game.winner is None:
            game.next_player()

    assert game.winner is game.players[0]


def test_a_correction_that_wins_turns_the_later_darts_into_shadows():
    game = cricket()
    play(game, *interleave(("T20 T19 T18", "T17 T16 T15", "50", "1 2 3")))

    assert game.winner is None
    game.replace_dart(0, dart("25"))

    assert game.winner is game.players[0]
    assert game.current_turn.darts == darts("25")
    assert game.shadow_darts == darts("2", "3")

    game.undo()
    assert game.winner is None
    assert game.current_turn.darts == darts("2", "3")
    assert game.shadow_darts == []


def test_marks_per_round_count_closing_and_scoring_marks():
    game = cricket()
    play(game, "T20 T20 5", "T20", "T20 T20 T20")

    player = game.progress.players[0]
    assert player.counted_marks == 3 + 3
    assert player.darts == 6
    assert game.progress.turn_marks == [6, 3, 0]


def test_a_handover_fills_the_visit_with_misses():
    game = cricket()
    play(game, "T20")

    assert game.next_player() == 2
    assert game.turns[0].darts == darts("T20", "0", "0")
