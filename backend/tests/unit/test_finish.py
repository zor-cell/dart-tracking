from app.api.features.game.domain.around_the_clock import CLOCK_TARGETS, ClockOptions
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.turn import Turn
from tests.unit.darts import new_game, play


def race_at(*needs: int, catch_up=False, play_on=False, variant=GameVariant.X01):
    """Seat after seat needing these points, one opening round already thrown,
    seat 0 to throw."""
    game = new_game(len(needs), variant=variant)
    game.finish = FinishRules(catch_up=catch_up, play_on=play_on)
    game.turns = [
        Turn(player_id=seat, darts=[Dart(value=301 - need, multiplier=1)])
        for seat, need in enumerate(needs)
    ]
    game.turns.append(Turn(player_id=0))
    return game


def ids(players):
    return [player.id for player in players]


def needs(game):
    return [game.remaining(player.id) for player in game.players]


def test_without_rules_the_first_finish_wins_at_once():
    game = race_at(8, 16, catch_up=False)
    play(game, "D4")

    assert game.winner is game.players[0]


def test_catching_up_lets_the_rest_of_the_round_throw():
    game = race_at(8, 16, 40, catch_up=True)
    play(game, "D4")

    assert game.winner is None
    assert game.darts_remaining == 0
    assert game.race().finishers == [0]

    play(game, "0 0 0", "0 0 0", "0 0 0")
    assert game.current_player_index == 2
    assert game.winner is game.players[0]


def test_a_finisher_last_in_the_round_wins_at_once():
    game = race_at(40, 16, catch_up=True)
    play(game, "0 0 0", "D8")

    assert game.winner is game.players[1]


def test_a_shared_finish_replays_the_round_from_where_it_began():
    game = race_at(8, 16, catch_up=True)
    play(game, "D4", "D8")

    assert game.winner is None
    assert needs(game) == [0, 0]
    assert game.race().finishers == [0, 1]
    assert game.darts_remaining == 0

    game.next_player()
    assert game.current_player_index == 0
    assert needs(game) == [8, 16]
    assert game.race().finishers == []


def test_the_replay_repeats_until_one_finishes_alone():
    game = race_at(8, 16, catch_up=True)
    play(game, "D4", "D8", "D4", "D8", "0 0 0", "D8")

    assert game.winner is game.players[1]


def test_a_tiebreak_leaves_the_others_waiting():
    game = race_at(8, 16, 40, catch_up=True)
    play(game, "D4", "D8", "0 0 0")

    state = game.race()
    assert state.finishers == [0, 1]
    assert state.waiting == []
    game.next_player()
    assert game.current_player_index == 0
    state = game.race()
    assert state.finishers == []
    assert state.waiting == [2]
    play(game, "0 0 0")
    game.next_player()
    assert game.current_player_index == 1
    play(game, "0 0 0")
    game.next_player()
    assert game.current_player_index == 0


def test_undoing_the_shared_finish_undoes_the_tiebreak():
    game = race_at(8, 16, catch_up=True)
    play(game, "D4", "D8")
    game.undo()

    assert game.race().finishers == [0]
    assert needs(game) == [0, 16]


def test_playing_on_places_everyone_in_finishing_order():
    game = race_at(8, 16, 40, play_on=True)
    play(game, "D4")

    assert game.winner is None
    assert game.race().places == [0]

    game.next_player()
    assert game.current_player_index == 1
    play(game, "0 0 0", "0 0 0")
    game.next_player()
    assert game.current_player_index == 1

    play(game, "D8")
    state = game.race()
    assert state.places == [0, 1, 2]
    assert state.finishers == [0, 1]
    assert game.winner is game.players[0]


def test_the_loser_of_a_tiebreak_takes_the_next_place():
    game = race_at(8, 16, 40, 60, catch_up=True, play_on=True)
    play(game, "D4", "D8", "0 0 0", "0 0 0", "0 0 0", "D8")

    state = game.race()
    assert state.places == [1, 0]
    assert state.finishers == [0, 1]
    assert state.waiting == []
    game.next_player()
    assert game.current_player_index == 2


def test_a_tiebreak_of_three_narrows_and_the_last_one_left_comes_last():
    game = race_at(8, 16, 32, 60, catch_up=True, play_on=True)
    play(game, "D4", "D8", "D16", "0 0 0", "D4", "D8", "0 0 0")
    game.next_player()

    state = game.race()
    assert state.finishers == []
    assert state.waiting == [2, 3]
    assert needs(game)[:3] == [8, 16, 32]

    play(game, "0 0 0", "D8")
    state = game.race()
    assert state.places == [1, 0, 2, 3]
    assert game.winner is game.players[1]


def test_a_finished_player_is_not_reset_in_elimination():
    game = new_game(3, variant=GameVariant.ELIMINATION)
    game.finish = FinishRules(play_on=True)
    game.turns = [
        Turn(player_id=0, darts=[Dart(value=301 - 40, multiplier=1)]),
        Turn(player_id=1, darts=[Dart(value=301 - 38, multiplier=1)]),
        Turn(player_id=2, darts=[Dart(value=1, multiplier=1)]),
        Turn(player_id=0),
    ]
    play(game, "D20", "D19")

    assert game.race().places == [0, 1, 2]
    assert needs(game)[:2] == [0, 0]


def test_around_the_clock_catches_up_and_replays_too():
    game = new_game(2, variant=GameVariant.AROUND_THE_CLOCK, options=ClockOptions())
    game.finish = FinishRules(catch_up=True)
    bull = len(CLOCK_TARGETS) - 1
    game.turns = [
        Turn(player_id=0, darts=[Dart(value=n, multiplier=1) for n in range(1, 21)]),
        Turn(player_id=1, darts=[Dart(value=n, multiplier=1) for n in range(1, 21)]),
        Turn(player_id=0),
    ]
    play(game, "25", "25")

    assert game.winner is None
    assert [player.position for player in game.progress.players.values()] == [bull + 1] * 2
    game.next_player()
    assert [player.position for player in game.progress.players.values()] == [bull, bull]
    play(game, "0 0 0", "50")
    assert game.winner is game.players[1]


def test_variants_without_a_race_ignore_the_rules():
    players = new_game(2).players
    game = Game(id="g", mode=None, players=players, variant=GameVariant.CRICKET,
                checkout_mode=None, finish=FinishRules(catch_up=True, play_on=True))

    assert game.finish == FinishRules()
