import pytest

from app.api.features.announcement.domain.calls import TurnCall
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.quick_start import GameSetup
from app.api.features.game.domain.training import (
    TrainingGoal,
    TrainingOptions,
    TrainingRing,
    random_fields,
)
from tests.unit.darts import dart, new_game, play

T19, D16, BULL = (19, 3), (16, 2), (25, 2)
LABELS = {1: "", 2: "D", 3: "T"}


def training(players=1, **options):
    return new_game(players, variant=GameVariant.TRAINING, options=TrainingOptions(**options))


def label(field):
    value, multiplier = field
    return "50" if field == BULL else f"{LABELS[multiplier]}{value}"


def standing(game, seat=0):
    return game.progress.players[seat]


def test_a_training_keeps_no_points_and_nobody_wins():
    game = training()
    play(game, "T20 T20 T20", "50 50 50")

    assert game.mode is None
    assert game.winner is None
    assert not game.over
    assert standing(game).darts == 6
    assert standing(game).target is None


def test_free_training_keeps_the_average_and_the_last_visit():
    game = training()
    play(game, "T20 20 0", "1")

    assert game.average(0) == pytest.approx(3 * 81 / 4)
    assert game.last_visit(0) == 80


def test_own_fields_stay_until_hit_and_then_follow_in_order():
    game = training(goal=TrainingGoal.FIELDS, fields=(T19, D16))

    assert standing(game).target == T19
    play(game, "19 0 0", "T19 16")
    assert standing(game).target == D16
    play(game, "D16")

    player = standing(game)
    assert player.target == T19
    assert (player.tallies[T19].darts, player.tallies[T19].hits) == (4, 1)
    assert (player.tallies[D16].darts, player.tallies[D16].hits) == (2, 1)
    assert game.progress.turn_hits == [0, 2]


def test_every_player_walks_the_fields_on_their_own():
    game = training(2, goal=TrainingGoal.FIELDS, fields=(T19, D16))
    play(game, "T19", "0", "0")

    assert standing(game, 0).target == D16
    assert standing(game, 1).target == T19


def test_a_field_takes_as_many_hits_as_asked_before_the_next_comes_up():
    game = training(goal=TrainingGoal.FIELDS, fields=(T19, D16), repeats=3)
    play(game, "T19 T19")

    assert (standing(game).target, standing(game).left) == (T19, 1)
    game.register_dart(dart("T19"))
    assert (standing(game).target, standing(game).left) == (D16, 3)


def test_shuffled_fields_come_up_at_random_but_never_twice_running():
    game = training(goal=TrainingGoal.FIELDS, fields=(T19, D16, BULL), shuffle=True, seed=5)
    seen = []
    for _ in range(12):
        seen.append(standing(game).target)
        game.register_dart(dart(label(seen[-1])))
        if game.darts_remaining == 0:
            game.next_player()

    assert set(seen) == {T19, D16, BULL}
    assert all(first != second for first, second in zip(seen, seen[1:]))
    assert seen != [T19, D16, BULL] * 4


def test_only_the_exact_field_is_a_hit():
    game = training(goal=TrainingGoal.FIELDS, fields=(T19,))
    play(game, "19 D19 T19")

    assert standing(game).hits == 1


@pytest.mark.parametrize(
    ("ring", "count"),
    [
        (TrainingRing.SINGLE, 21),
        (TrainingRing.DOUBLE, 21),
        (TrainingRing.TRIPLE, 20),
        (TrainingRing.MIXED, 62),
    ],
)
def test_random_targets_come_from_the_chosen_ring(ring, count):
    fields = random_fields(ring)

    assert len(set(fields)) == count
    assert (25, 3) not in fields
    game = training(goal=TrainingGoal.RANDOM, ring=ring, seed=7)
    assert standing(game).target in fields


def test_a_random_target_stays_until_it_is_hit_and_then_changes():
    game = training(goal=TrainingGoal.RANDOM, ring=TrainingRing.TRIPLE, seed=3)
    first = standing(game).target
    miss = "T1" if first != (1, 3) else "T2"

    play(game, f"{miss} {miss}")
    assert standing(game).target == first

    game.register_dart(dart(label(first)))
    second = standing(game).target
    assert second != first
    assert standing(game).hits == 1
    assert standing(game).tallies[first].darts == 3


def test_the_same_seed_names_the_same_targets():
    games = [training(goal=TrainingGoal.RANDOM, seed=11) for _ in range(2)]
    other = training(goal=TrainingGoal.RANDOM, seed=12)
    drawn = []
    for game in (*games, other):
        targets = []
        for _ in range(6):
            targets.append(standing(game).target)
            game.register_dart(dart(label(targets[-1])))
            if game.darts_remaining == 0:
                game.next_player()
        drawn.append(targets)

    assert drawn[0] == drawn[1]
    assert drawn[0] != drawn[2]


def test_ending_closes_the_game_and_going_back_reopens_it():
    game = training()
    play(game, "T20")
    game.set_ended(True)

    assert game.over
    assert game.winner is None
    assert game.darts_remaining == 0
    assert game.register_dart(dart("20")) is False
    game.add_dart(dart("20"))
    assert game.next_player() == 0
    assert len(game.current_turn.darts) == 1
    assert game.last_closed_turn(0) == 0

    game.set_ended(False)
    assert not game.over
    assert game.register_dart(dart("20")) is True


def test_an_empty_open_visit_is_not_the_last_one_once_ended():
    game = training()
    play(game, "T20 T20 T20", "")
    game.set_ended(True)

    assert game.last_visit(0) == 180


def test_a_game_that_is_won_cannot_be_ended_by_hand():
    game = new_game()
    revision = game.revision
    game.set_ended(True)

    assert not game.ended
    assert game.revision == revision


def test_the_call_names_the_field_to_hit():
    game = training(goal=TrainingGoal.FIELDS, fields=(T19,))

    assert TurnCall.of(game) == TurnCall("P0", None, T19)
    assert TurnCall.of(training()) == TurnCall("P0", None, None)


def test_the_quick_start_ignores_the_seed():
    setups = [
        GameSetup.of(GameVariant.TRAINING, None, None, TrainingOptions(TrainingGoal.RANDOM, seed=seed))
        for seed in (1, 2)
    ]

    assert setups[0] == setups[1]
