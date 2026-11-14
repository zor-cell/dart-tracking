from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from app.api.features.game.domain.target import Target, finishing_double
from app.api.features.game.domain.training import TrainingGoal, TrainingOptions
from tests.unit.darts import leg_at, new_game, play


def test_a_target_is_hit_in_its_ring_or_in_any_ring_of_the_number():
    assert Target(16, 2).hit_by(16, 2)
    assert not Target(16, 2).hit_by(16, 1)
    assert Target(16, None).hit_by(16, 3)
    assert not Target(16, None).hit_by(8, 2)
    assert not Target(16, None).hit_by(16, 0)


def test_only_a_one_dart_finish_names_a_double():
    assert finishing_double(32) == Target(16, 2)
    assert finishing_double(50) == Target(25, 2)
    assert finishing_double(41) is None
    assert finishing_double(42) is None
    assert finishing_double(1) is None


def test_around_the_clock_aims_every_dart_at_the_number_it_stood_on():
    options = ClockOptions(zone=ClockZone.ANY)
    game = new_game(1, variant=GameVariant.AROUND_THE_CLOCK, options=options)

    play(game, "1 5 2", "D3")

    assert game.targets() == [
        [Target(1, None), Target(2, None), Target(2, None)],
        [Target(3, None)],
    ]


def test_around_the_clock_on_doubles_aims_at_the_double():
    options = ClockOptions(zone=ClockZone.DOUBLE)
    game = new_game(1, variant=GameVariant.AROUND_THE_CLOCK, options=options)

    play(game, "D1 2")

    assert game.targets() == [[Target(1, 2), Target(2, 2)]]


def test_training_aims_at_the_field_that_was_up():
    options = TrainingOptions(goal=TrainingGoal.FIELDS, fields=((19, 3), (16, 2)))
    game = new_game(1, variant=GameVariant.TRAINING, options=options)

    play(game, "19 T19 D8")

    assert game.targets() == [[Target(19, 3), Target(19, 3), Target(16, 2)]]


def test_a_free_training_has_no_targets():
    game = new_game(1, variant=GameVariant.TRAINING, options=TrainingOptions())

    play(game, "T20 20")

    assert game.targets() == [[None, None]]


def test_killer_aims_at_the_own_number_until_it_makes_a_killer():
    options = KillerOptions(numbers=(7, 12), zone=KillerZone.DOUBLE)
    game = new_game(2, variant=GameVariant.KILLER, options=options)

    play(game, "7 D7 D12", "5")

    assert game.targets() == [[Target(7, 2), Target(7, 2), None], [Target(12, 2)]]


def test_x01_aims_at_the_double_once_one_dart_can_finish():
    game = leg_at(72)

    play(game, "20 20 D8", "0", "D8")

    own = [aimed for turn, aimed in zip(game.turns, game.targets()) if turn.player_id == 0]
    assert own[-2:] == [[None, None, Target(16, 2)], [Target(8, 2)]]


def test_single_out_and_cricket_name_no_target():
    single_out = leg_at(32, checkout=CheckoutMode.SINGLE_OUT)
    cricket = new_game(variant=GameVariant.CRICKET, options=CricketOptions())

    play(single_out, "16")
    play(cricket, "T20")

    assert all(target is None for turn in single_out.targets() for target in turn)
    assert cricket.targets() == [[None]]
