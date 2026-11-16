from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.api.features.game.domain.around_the_clock import ClockOptions
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.personal_training import PersonalOptions, PlanBlock
from app.api.features.game.domain.training import TrainingGoal, TrainingOptions
from tests.unit.darts import dart, new_game, play

S20, S19, S18 = (20, 1), (19, 1), (18, 1)


def labels(game):
    return [thrown.label for thrown in game.current_turn.darts]


def mixed_plan():
    options = PersonalOptions(blocks=(PlanBlock((S20, S19, S18), 9),))
    return new_game(1, variant=GameVariant.PERSONAL, options=options)


def own_fields():
    options = TrainingOptions(goal=TrainingGoal.FIELDS, fields=(S20, S19, S18))
    return new_game(1, variant=GameVariant.TRAINING, options=options)


def clock():
    return new_game(1, variant=GameVariant.AROUND_THE_CLOCK, options=ClockOptions())


@pytest.mark.parametrize("game", [mixed_plan, own_fields], ids=["personal", "fields"])
def test_a_missed_first_dart_goes_back_to_where_it_was_thrown(game):
    game = game()
    play(game, "19 18")
    game.add_dart(dart("20"))

    assert labels(game) == ["20", "19", "18"]
    assert game.progress.turn_hits == [3]


def test_a_missed_middle_dart_goes_between():
    game = mixed_plan()
    play(game, "20 18")
    game.add_dart(dart("19"))

    assert labels(game) == ["20", "19", "18"]


def test_a_dart_that_hits_nowhere_better_stays_last():
    game = mixed_plan()
    play(game, "20 0")
    game.add_dart(dart("5"))

    assert labels(game) == ["20", "0", "5"]


def test_a_real_miss_keeps_its_place_between_two_hits():
    game = mixed_plan()
    play(game, "20 18")
    game.add_dart(dart("5"))

    assert labels(game) == ["20", "5", "18"]
    assert game.progress.turn_hits == [2]


def test_around_the_clock_puts_the_dart_where_the_count_goes_on():
    game = clock()
    play(game, "2 3")
    game.add_dart(dart("1"))

    assert labels(game) == ["1", "2", "3"]


@pytest.mark.parametrize(
    "game",
    [
        lambda: new_game(1, variant=GameVariant.TRAINING, options=TrainingOptions()),
        lambda: new_game(1),
    ],
    ids=["free training", "x01"],
)
def test_without_a_field_per_dart_the_dart_goes_last(game):
    game = game()
    play(game, "19 18")
    game.add_dart(dart("20"))

    assert labels(game) == ["19", "18", "20"]


def test_the_inserted_dart_takes_its_successors_time():
    game = mixed_plan()
    thrown = datetime(2026, 11, 16, 19, 0, tzinfo=UTC)
    game.register_dart(replace(dart("19"), thrown_at=thrown))
    game.add_dart(replace(dart("20"), thrown_at=datetime(2026, 11, 16, 19, 5, tzinfo=UTC)))

    assert [d.thrown_at for d in game.current_turn.darts] == [thrown, thrown]
