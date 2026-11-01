from datetime import UTC, datetime, timedelta

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.play_time import play_time
from tests.unit.darts import dart, new_game

START = datetime(2026, 11, 1, 20, 0, tzinfo=UTC)


def at(seconds: int) -> datetime:
    return START + timedelta(seconds=seconds)


def test_stamp_dates_new_darts_and_the_visit_handed_over():
    game = new_game()
    game.register_dart(dart("20"))
    game.stamp(at(5))
    game.register_dart(dart("20"))
    game.stamp(at(10))
    game.next_player()
    game.stamp(at(20))

    thrown = [d.thrown_at for d in game.turns[0].darts]
    assert thrown == [at(5), at(10), at(20)]
    assert game.turns[0].ended_at == at(20)
    assert game.current_turn.ended_at is None


def test_undo_reopens_the_visit_and_replace_keeps_the_time():
    game = new_game()
    game.register_dart(dart("20"))
    game.stamp(at(5))
    game.next_player()
    game.stamp(at(10))
    game.undo()
    game.stamp(at(15))
    game.replace_dart(0, dart("T20"))
    game.stamp(at(20))

    assert game.current_turn.ended_at is None
    assert game.current_turn.darts[0].thrown_at == at(5)


def test_the_winning_visit_ends_with_the_win():
    game = new_game(players=1, checkout=CheckoutMode.SINGLE_OUT)
    for label in ("T20", "T20", "T20"):
        game.register_dart(dart(label))
    game.stamp(at(10))
    game.next_player()
    game.stamp(at(20))
    for label in ("T20", "T20", "1"):
        game.register_dart(dart(label))
    game.stamp(at(30))

    assert game.winner is not None
    assert game.current_turn.ended_at == at(30)


def test_play_time_leaves_out_breaks():
    game = new_game()
    game.register_dart(dart("20"))
    game.stamp(at(60))
    game.next_player()
    game.stamp(at(90))
    game.register_dart(dart("20"))
    game.stamp(at(90 + 3 * 3600))

    # 60 s to the first dart, 30 s to the handover; the three hours are a break.
    assert play_time(game, START) == timedelta(seconds=90)


def test_play_time_needs_every_dart_dated():
    game = new_game()
    game.register_dart(dart("20"))

    assert play_time(game, START) is None
    assert play_time(new_game(), START) is None
