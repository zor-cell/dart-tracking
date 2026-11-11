import pytest

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.game_variant import GameVariant
from tests.unit.darts import dart, darts, new_game, play

ONE_TO_TWENTY = [
    " ".join(str(n) for n in range(start, min(start + 3, 21))) for start in range(1, 21, 3)
]


def round_the_board(game, ring=""):
    """Player 0 alone hits 1 to 20 in that ring, handing over after each visit."""
    for visit in ONE_TO_TWENTY:
        play(game, " ".join(ring + label for label in visit.split()))
        game.next_player()


def clock(players=2, zone=ClockZone.ANY, skip=False):
    options = ClockOptions(zone=zone, skip=skip)
    return new_game(players, variant=GameVariant.AROUND_THE_CLOCK, options=options)


def target(game, seat=0):
    return game.progress.players[seat].target


def test_play_starts_on_one():
    game = clock()

    assert target(game) == 1
    assert game.mode is None


def test_hits_move_on_one_target_each_within_a_visit():
    game = clock()
    play(game, "1 2 3")

    assert target(game) == 4


def test_a_miss_or_the_wrong_number_stays_put():
    game = clock()
    play(game, "2 0 20")

    assert target(game) == 1
    assert game.progress.players[0].hits == 0
    assert game.progress.players[0].darts == 3


@pytest.mark.parametrize("label", ["1", "D1", "T1"])
def test_any_ring_counts_by_default(label):
    game = clock()
    play(game, label)

    assert target(game) == 2


@pytest.mark.parametrize(
    ("zone", "label", "hit"),
    [
        (ClockZone.DOUBLE, "D1", True),
        (ClockZone.DOUBLE, "1", False),
        (ClockZone.DOUBLE, "T1", False),
        (ClockZone.TRIPLE, "T1", True),
        (ClockZone.TRIPLE, "D1", False),
    ],
)
def test_a_zone_counts_its_ring_only(zone, label, hit):
    game = clock(zone=zone)
    play(game, label)

    assert target(game) == (2 if hit else 1)


def test_the_bull_comes_after_twenty():
    game = clock(1)
    round_the_board(game)

    assert target(game) == 25


@pytest.mark.parametrize(
    ("zone", "label", "won"),
    [
        (ClockZone.ANY, "25", True),
        (ClockZone.ANY, "50", True),
        (ClockZone.DOUBLE, "25", False),
        (ClockZone.DOUBLE, "50", True),
        (ClockZone.TRIPLE, "50", True),
    ],
)
def test_the_bull_finishes(zone, label, won):
    game = clock(1, zone=zone)
    round_the_board(game, {ClockZone.ANY: "", ClockZone.DOUBLE: "D", ClockZone.TRIPLE: "T"}[zone])
    assert target(game) == 25
    play(game, label)

    assert (game.winner is not None) is won


def test_the_first_player_through_wins_at_once():
    game = clock()
    for visit in ONE_TO_TWENTY:
        play(game, visit, "0")
        game.next_player()
    play(game, "25")

    assert game.winner is game.players[0]
    assert game.darts_remaining == 2
    assert not game.register_dart(dart("1"))
    assert game.shadow_darts == darts("1")


def test_skipping_moves_on_by_the_ring():
    game = clock(skip=True)
    play(game, "D1 T3")

    assert target(game) == 6


def test_without_skipping_a_triple_moves_on_one():
    game = clock()
    play(game, "T1")

    assert target(game) == 2


def test_skipping_never_passes_the_bull():
    game = clock(1, skip=True)
    for visit in ONE_TO_TWENTY[:-1]:
        play(game, visit)
        game.next_player()
    play(game, "T19")

    assert target(game) == 25
    assert game.winner is None


def test_steps_and_hits_are_kept_per_visit():
    game = clock()
    play(game, "1 1 2", "1", "3 0 4")

    assert game.progress.turn_steps == [2, 1, 2]
    assert game.progress.players[0].hits == 4
    assert game.progress.players[0].darts == 6
