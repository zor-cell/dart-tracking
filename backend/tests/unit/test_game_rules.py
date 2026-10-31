import pytest

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_variant import GameVariant
from tests.unit.darts import dart, darts, leg_at, new_game

DOUBLE_OUT = CheckoutMode.DOUBLE_OUT
SINGLE_OUT = CheckoutMode.SINGLE_OUT


def throw(game, *labels):
    for label in labels:
        game.register_dart(dart(label))


@pytest.mark.parametrize(
    ("checkout", "remaining", "thrown", "busted", "won"),
    [
        (DOUBLE_OUT, 40, ["D20"], False, True),
        (DOUBLE_OUT, 50, ["50"], False, True),
        (DOUBLE_OUT, 40, ["20", "20"], True, False),
        (DOUBLE_OUT, 25, ["25"], True, False),
        (DOUBLE_OUT, 40, ["T13"], True, False),
        (DOUBLE_OUT, 40, ["T20"], True, False),
        (DOUBLE_OUT, 40, ["20", "D5"], False, False),
        (SINGLE_OUT, 40, ["20", "20"], False, True),
        (SINGLE_OUT, 1, ["1"], False, True),
        (SINGLE_OUT, 40, ["T13"], False, False),
        (SINGLE_OUT, 40, ["T20"], True, False),
    ],
)
def test_bust_and_finish(checkout, remaining, thrown, busted, won):
    game = leg_at(remaining, checkout)
    throw(game, *thrown)

    assert game.current_turn.busted is busted
    assert (game.winner is not None) is won
    assert game.current_turn.darts == darts(*thrown)
    if busted:
        assert game.remaining(0) == remaining
        assert game.darts_remaining == 0


def test_closed_visit_parks_darts_as_shadows_up_to_three_physical_darts():
    game = leg_at(40)
    throw(game, "T20")
    revision = game.revision

    assert game.register_dart(dart("1")) is False
    assert game.register_dart(dart("2")) is False
    assert game.register_dart(dart("3")) is False

    assert game.shadow_darts == darts("1", "2")
    assert game.current_turn.darts == darts("T20")
    assert game.revision == revision + 2


def test_correcting_the_bust_books_the_shadows_in_throwing_order():
    game = leg_at(40)
    throw(game, "T20", "5", "D10")

    game.replace_dart(0, dart("5"))

    assert game.current_turn.darts == darts("5", "5", "D10")
    assert not game.current_turn.busted
    assert game.shadow_darts == []
    assert game.remaining(0) == 10


def test_correction_rescores_only_until_the_visit_closes_again():
    game = leg_at(40)
    throw(game, "D20", "20", "20")

    game.replace_dart(0, dart("10"))

    assert game.current_turn.darts == darts("10", "20", "20")
    assert game.current_turn.busted


def test_order_decides_the_bust():
    game = leg_at(40)
    throw(game, "20", "D10")
    assert game.winner is not None

    game.move_dart(1, 0)

    assert game.current_turn.darts == darts("D10", "20")
    assert game.current_turn.busted
    assert game.winner is None


def test_manual_dart_goes_before_the_dart_that_closed_the_visit():
    game = leg_at(40)
    throw(game, "D20")

    game.add_dart(dart("5"))

    assert game.current_turn.darts == darts("5", "D20")
    assert game.current_turn.busted
    assert game.winner is None


def test_manual_dart_into_a_full_visit_changes_nothing():
    game = new_game()
    throw(game, "1", "2", "3")
    revision = game.revision

    game.add_dart(dart("4"))

    assert game.current_turn.darts == darts("1", "2", "3")
    assert game.revision == revision


def test_undo_takes_back_the_winning_dart():
    game = leg_at(40)
    throw(game, "D20")

    game.undo()

    assert game.winner is None
    assert game.current_turn.darts == []
    assert game.darts_remaining == 3


def test_undo_on_an_empty_visit_reopens_the_previous_one():
    game = new_game()
    throw(game, "T20", "5")
    game.next_player()

    game.undo()

    assert game.current_player_index == 0
    assert game.current_turn.darts == darts("T20", "5", "0")
    assert len(game.turns) == 1


def test_undo_at_the_start_changes_nothing():
    game = new_game()

    game.undo()

    assert game.revision == 0
    assert not game.can_undo


@pytest.mark.parametrize("index", [-1, 2, 5])
def test_corrections_outside_the_visit_change_nothing(index):
    game = new_game()
    throw(game, "1", "2")
    revision = game.revision

    game.remove_dart(index)
    game.replace_dart(index, dart("T20"))
    game.move_dart(index, 0)
    game.move_dart(0, index)
    game.move_dart(1, 1)

    assert game.current_turn.darts == darts("1", "2")
    assert game.revision == revision


def test_remove_dart_takes_one_from_the_middle():
    game = new_game()
    throw(game, "1", "2", "3")

    game.remove_dart(1)

    assert game.current_turn.darts == darts("1", "3")
    assert game.darts_remaining == 1


def test_next_player_twice_does_not_skip_anyone():
    game = new_game(players=3)
    throw(game, "1")

    game.next_player()
    revision = game.revision
    game.next_player()

    assert game.current_player_index == 1
    assert game.revision == revision


def test_handover_books_the_missing_darts_as_misses():
    game = new_game()
    throw(game, "T20")

    assert game.next_player() == 2
    assert game.turns[0].darts == darts("T20", "0", "0")
    assert game.current_player_index == 1


def test_handover_after_a_bust_fills_nothing():
    game = leg_at(40)
    throw(game, "T20")

    assert game.next_player() == 0
    assert game.turns[2].darts == darts("T20")
    assert game.current_player_index == 1


@pytest.mark.parametrize("thrown", [[], ["D20"]], ids=["empty visit", "won"])
def test_handover_without_a_visit_to_end_changes_nothing(thrown):
    game = leg_at(40)
    throw(game, *thrown)
    revision = game.revision

    assert game.next_player() == 0
    assert game.revision == revision


def test_handover_drops_the_shadows_and_wraps_around():
    game = leg_at(40)
    throw(game, "T20", "5")

    game.next_player()
    assert game.current_player_index == 1
    assert game.shadow_darts == []

    throw(game, "1")
    game.next_player()
    assert game.current_player_index == 0


def test_no_handover_after_the_leg_is_won():
    game = leg_at(40)
    throw(game, "D20")

    game.next_player()

    assert game.current_player_index == 0
    assert game.winner is not None


def test_elimination_resets_whoever_was_drawn_level_with():
    game = new_game(variant=GameVariant.ELIMINATION)
    throw(game, "T20")
    game.next_player()
    throw(game, "T20")

    assert game.remaining(0) == 301
    assert game.remaining(1) == 241


def test_each_turn_starts_from_what_the_others_left_standing():
    game = new_game(variant=GameVariant.ELIMINATION)
    throw(game, "T20")
    game.next_player()
    throw(game, "T20")
    game.next_player()
    throw(game, "20")

    assert game.remaining_before_turns() == [301, 301, 301]


def test_elimination_leaves_players_on_zero_alone():
    game = new_game(players=3, variant=GameVariant.ELIMINATION)
    throw(game, "0")

    assert [game.remaining(seat) for seat in range(3)] == [301, 301, 301]


def test_elimination_reset_depends_on_the_score_when_the_dart_landed():
    game = new_game(variant=GameVariant.ELIMINATION)
    throw(game, "20")
    game.next_player()
    throw(game, "10", "10", "5")

    assert game.remaining(0) == 301
    assert game.remaining(1) == 276


def test_elimination_suggests_the_cheapest_reset():
    game = new_game(players=3, variant=GameVariant.ELIMINATION)
    throw(game, "T20", "T20")
    game.next_player()
    throw(game, "T20")
    game.next_player()

    assert game.elimination == ["T20"]


def test_suggestions_stop_once_the_leg_is_won():
    game = leg_at(40)
    throw(game, "D20")

    assert game.checkout is None
    assert game.setup is None


def test_setup_is_offered_only_for_the_last_dart():
    game = leg_at(101)
    assert game.setup is None

    throw(game, "1", "1")

    assert game.checkout is None
    assert game.setup is not None
    assert game.setup.leave + sum(dart(label).points for label in game.setup.darts) == 99
