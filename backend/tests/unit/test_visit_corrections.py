from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.correction_consequence import CorrectionConsequence
from app.api.features.game.domain.cricket import CricketOptions
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from tests.unit.darts import dart, darts, new_game, play
from tests.unit.test_finish import race_at


def labels(turn):
    return [d.label for d in turn.darts]


def test_a_correction_in_an_earlier_visit_busts_a_later_one():
    game = new_game()
    play(game, "T20 T20 T19", "0 0 0", "T20 T20 2", "0 0 0")
    game.next_player()
    assert game.remaining(0) == 2

    game.replace_dart(2, dart("T20"), turn=0)

    assert game.turns[2].busted
    assert game.remaining(0) == 121
    assert labels(game.turns[2]) == ["T20", "T20", "2"]


def test_a_visit_that_no_longer_busts_is_filled_to_three_darts():
    game = new_game()
    play(game, "T20 T20 T20", "0 0 0", "T20 T20", "0 0 0")
    game.next_player()
    assert game.turns[2].busted

    game.replace_dart(0, dart("20"), turn=0)

    assert not game.turns[2].busted
    assert labels(game.turns[2]) == ["T20", "T20", "0"]
    assert game.remaining(0) == 41


def test_an_earlier_win_waits_for_confirmation_and_then_drops_the_later_visits():
    game = new_game()
    play(game, "T20 T20 T20", "0 0 0", "T20 T19 D1", "0 0 0", "1 1 1")
    revision, turns = game.revision, len(game.turns)

    consequence = game.replace_dart(2, dart("D2"), turn=2)

    assert consequence == CorrectionConsequence(won_at=2, winner_id=0)
    assert (game.revision, len(game.turns), game.winner) == (revision, turns, None)

    assert game.replace_dart(2, dart("D2"), turn=2, confirmed=True) is None
    assert len(game.turns) == 3
    assert game.winner is game.players[0]
    assert game.win_confirmed
    assert game.current_player.id == 0


def test_darts_after_a_finish_moved_into_a_closed_visit_are_dropped():
    game = new_game(checkout=CheckoutMode.SINGLE_OUT)
    play(game, "T20 T20 T20", "0 0 0", "0 0 0", "0 0 0", "T20 T20 T20", "0")
    assert game.turns[4].busted

    game.replace_dart(0, dart("1"), turn=2, confirmed=True)

    assert labels(game.turns[4]) == ["T20", "T20"]
    assert len(game.turns) == 5
    assert game.winner is game.players[0]


def test_removing_a_dart_from_a_closed_visit_leaves_a_miss_without_its_tip():
    game = new_game()
    game.register_dart(Dart(value=20, multiplier=1, position=(1.0, 90.0)))
    play(game, "5 1", "0 0 0")

    game.remove_dart(0, turn=0)

    assert game.turns[0].darts == darts("0", "5", "1")
    assert game.turns[0].darts[0].position is None
    assert game.remaining(0) == 295


def test_a_closed_visit_keeps_its_darts_while_the_open_one_gets_corrected():
    game = new_game()
    play(game, "20 20 20", "5")

    game.replace_dart(0, dart("T5"))

    assert labels(game.turns[0]) == ["20", "20", "20"]
    assert labels(game.current_turn) == ["T5"]


def test_a_correction_that_knocks_a_player_out_earlier_asks_first():
    game = new_game(3, variant=GameVariant.KILLER, options=KillerOptions((20, 5, 1), 1, KillerZone.DOUBLE))
    play(game, "D20 5 0", "0 0 0", "0 0 0")
    game.next_player()

    assert game.replace_dart(1, dart("D5"), turn=0) == CorrectionConsequence(out=(1,))
    assert not game.progress.players[1].out

    game.replace_dart(1, dart("D5"), turn=0, confirmed=True)
    assert game.progress.players[1].out
    assert len(game.turns) == 4
    assert game.current_player.id == 0


def test_a_player_knocked_out_by_a_correction_loses_the_open_visit():
    game = new_game(3, variant=GameVariant.KILLER, options=KillerOptions((20, 5, 1), 1, KillerZone.DOUBLE))
    play(game, "D20 5 0", "0 0 0", "0 0 0", "0 0 0")
    game.next_player()
    assert game.current_player.id == 1

    game.replace_dart(1, dart("D5"), turn=0, confirmed=True)

    assert len(game.turns) == 5
    assert game.current_player.id == 2
    assert game.current_turn.player_id == 2


def test_a_correction_that_places_a_player_earlier_voids_their_later_visits():
    game = race_at(8, 16, 40, play_on=True)
    play(game, "4 0 0", "0 0 0", "0 0 0", "D2")
    assert game.race().places == [0]

    consequence = game.replace_dart(0, dart("D4"), turn=3, confirmed=True)

    assert consequence is None
    state = game.race()
    assert state.places == [0]
    assert 6 in state.voided
    assert game.remaining(0) == 0


def test_a_cricket_win_moved_earlier_drops_the_visits_after_it():
    game = new_game(variant=GameVariant.CRICKET, options=CricketOptions())
    play(game, "T20 T19 T18", "0", "T17 T16 T15", "0", "50 0 0", "0", "0 0 0")

    consequence = game.replace_dart(1, dart("25"), turn=4)

    assert consequence == CorrectionConsequence(won_at=4, winner_id=0)
    game.replace_dart(1, dart("25"), turn=4, confirmed=True)
    assert len(game.turns) == 5
    assert game.winner is game.players[0]


def test_a_correction_outside_the_visits_changes_nothing():
    game = new_game()
    play(game, "20 20 20")
    revision = game.revision

    assert game.replace_dart(0, dart("T20"), turn=5) is None
    assert game.remove_dart(3, turn=0) is None
    assert game.revision == revision
