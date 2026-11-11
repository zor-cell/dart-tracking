import pytest

from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from tests.unit.darts import dart, darts, new_game, play

# Seat 0 owns 20, seat 1 owns 5, seat 2 owns 1.
NUMBERS = (20, 5, 1)


def killer(players=2, lives=3, zone=KillerZone.DOUBLE):
    options = KillerOptions(numbers=NUMBERS[:players], lives=lives, zone=zone)
    return new_game(players, variant=GameVariant.KILLER, options=options)


def standing(game, seat):
    return game.progress.players[seat]


def test_numbers_are_dealt_by_seat_without_options():
    game = new_game(3, variant=GameVariant.KILLER)

    assert [standing(game, seat).number for seat in range(3)] == [1, 2, 3]
    assert game.mode is None
    assert game.checkout is None


def test_hitting_the_own_double_makes_a_killer_without_costing_a_life():
    game = killer()
    play(game, "D20")

    assert standing(game, 0).killer
    assert standing(game, 0).lives == 3


def test_a_player_who_is_no_killer_cannot_take_lives():
    game = killer()
    play(game, "D5 D5 D5")

    assert standing(game, 1).lives == 3
    assert not standing(game, 0).killer


def test_a_killer_takes_a_life_with_each_hit_on_an_opponents_double():
    game = killer()
    play(game, "D20 D5 D5")

    assert standing(game, 1).lives == 1
    assert standing(game, 0).kills == 2


@pytest.mark.parametrize("label", ["5", "T5", "25", "50", "0", "D6"])
def test_only_the_zone_takes_a_life(label):
    game = killer()
    play(game, f"D20 {label}")

    assert standing(game, 1).lives == 3


def test_a_killer_hitting_the_own_double_loses_a_life_and_stays_a_killer():
    game = killer()
    play(game, "D20 D20")

    assert standing(game, 0).lives == 2
    assert standing(game, 0).killer
    assert standing(game, 0).kills == 0


def test_the_triple_zone_counts_triples_only():
    game = killer(zone=KillerZone.TRIPLE)
    play(game, "D20 T20 D5")

    assert standing(game, 0).killer
    assert standing(game, 1).lives == 3

    game.next_player()
    play(game, "0", "T5")
    assert standing(game, 1).lives == 2


def test_the_any_zone_counts_a_double_twice_and_a_triple_three_times():
    game = killer(lives=5, zone=KillerZone.ANY)
    play(game, "20 5 D5")

    assert standing(game, 0).killer
    assert standing(game, 1).lives == 2

    game.next_player()
    play(game, "0", "T5")
    assert standing(game, 1).lives == 0
    assert standing(game, 0).kills == 5


def test_the_last_player_with_lives_wins_at_once():
    game = killer()
    play(game, "D20 D5 D5", "0", "D5")

    assert game.winner is game.players[0]
    assert game.current_turn.darts == darts("D5")
    assert not game.register_dart(dart("1"))
    assert game.shadow_darts == darts("1")


def test_a_knocked_out_player_is_passed_over():
    game = killer(3)
    play(game, "D20 D5 D5", "0", "0", "D5")

    assert game.is_out(1)
    assert game.just_reset() == {1}
    game.next_player()

    assert game.current_player.id == 2
    assert game.winner is None


def test_knocking_yourself_out_ends_the_visit():
    game = killer(3, lives=1)
    play(game, "D20 D20")

    assert game.is_out(0)
    assert game.darts_remaining == 0
    assert not game.register_dart(dart("D5"))
    assert game.next_player() == 0
    assert game.current_player.id == 1


def test_knocking_yourself_out_hands_the_win_to_the_last_one_standing():
    game = killer(lives=1)
    play(game, "D20 D20")

    assert game.winner is game.players[1]


def test_undo_gives_a_life_back():
    game = killer()
    play(game, "D20 D5")
    game.undo()

    assert standing(game, 1).lives == 3
    assert standing(game, 0).killer


def test_a_correction_that_knocks_yourself_out_shadows_the_later_darts():
    game = killer(3, lives=1)
    play(game, "D20 1 D5")
    game.replace_dart(1, dart("D20"))

    assert game.is_out(0)
    assert game.current_turn.darts == darts("D20", "D20")
    assert game.shadow_darts == darts("D5")
    assert standing(game, 1).lives == 1


def test_a_manual_dart_goes_before_the_dart_that_closed_the_visit():
    game = killer(3, lives=1)
    play(game, "D20 D20")
    game.add_dart(dart("D5"))

    assert game.current_turn.darts == darts("D20", "D5", "D20")
    assert game.is_out(1)
    assert game.is_out(0)
    assert game.winner is game.players[2]
