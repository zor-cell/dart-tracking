from datetime import datetime

import pytest

from app.api.features.announcement.domain.calls import TurnCall
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.personal_training import (
    Baseline,
    PersonalFocus,
    PersonalLength,
    PersonalOptions,
    PlanBlock,
    aimed_at,
    plan_blocks,
)
from app.api.features.game.domain.target import Target
from app.api.features.game.services.personal_plan import build_plan
from app.api.features.statistics.domain.target_statistics import AimedDart, TargetStatistics
from app.api.features.statistics.domain.weakness import weaknesses
from tests.unit.darts import new_game, play

D16, D8, T19, D20, T20 = (16, 2), (8, 2), (19, 3), (20, 2), (20, 3)


def personal(*blocks: PlanBlock, baselines: tuple[Baseline, ...] = ()):
    options = PersonalOptions(blocks=blocks, baselines=baselines)
    return new_game(1, variant=GameVariant.PERSONAL, options=options)


def record(*shots: tuple[tuple[int, int], int, int]) -> TargetStatistics:
    """Statistics of darts at each field: (field, darts, hits); misses land beside it."""
    statistics = TargetStatistics()
    darts = []
    for (value, multiplier), count, hits in shots:
        for index in range(count):
            landed = (value, multiplier) if index < hits else (value, 1)
            darts.append(AimedDart(Target(value, multiplier), Dart(*landed)))
    statistics.add_game("game", datetime(2026, 11, 1), darts, False)
    return statistics


@pytest.mark.parametrize(
    ("fields", "length", "darts"),
    [
        ([D16, D8, T19], PersonalLength.SHORT, [12, 12, 12, 9]),
        ([D16, D8, T19], PersonalLength.MEDIUM, [24, 24, 24, 18]),
        ([D16, D8, T19], PersonalLength.LONG, [39, 39, 39, 33]),
        ([D16, D8], PersonalLength.MEDIUM, [36, 36, 18]),
        ([D16], PersonalLength.SHORT, [45]),
    ],
)
def test_a_plan_gives_each_field_a_block_and_closes_on_all_of_them(fields, length, darts):
    blocks = plan_blocks(fields, length)

    assert [block.darts for block in blocks] == darts
    assert all(block.darts % 3 == 0 for block in blocks)
    assert [block.fields for block in blocks[: len(fields)]] == [(field,) for field in fields]
    if len(fields) > 1:
        assert blocks[-1].fields == tuple(fields)


def test_the_mixed_block_takes_the_fields_dart_by_dart():
    blocks = (PlanBlock((D16,), 3), PlanBlock((D16, D8), 6))

    assert [aimed_at(blocks, dart) for dart in range(10)] == [
        (0, D16), (0, D16), (0, D16),
        (1, D16), (1, D8), (1, D16), (1, D8), (1, D16), (1, D8),
        None,
    ]


def test_hits_count_per_block_and_field_and_the_plan_moves_on():
    game = personal(PlanBlock((D16,), 3), PlanBlock((D8,), 3), PlanBlock((D16, D8), 6))

    play(game, "D16 16 0", "D8 D8 8", "")
    player = game.progress.players[0]

    assert (player.block, player.target, player.left) == (2, D16, 6)
    assert [(tally.darts, tally.hits) for tally in player.blocks] == [(3, 1), (3, 2), (0, 0)]
    assert (player.fields[D16].hits, player.fields[D8].hits) == (1, 2)
    assert game.targets() == [[Target(16, 2)] * 3, [Target(8, 2)] * 3, []]
    assert game.winner is None


def test_the_last_planned_dart_ends_the_training():
    game = personal(PlanBlock((D16,), 3), PlanBlock((D16, D8), 3))

    play(game, "D16 0 0", "0 D8 D16")

    assert game.winner is not None
    assert game.over
    player = game.progress.players[0]
    assert (player.target, player.hits, player.darts) == (None, 3, 6)
    assert game.darts_remaining == 0


def test_the_announcer_calls_the_planned_field():
    game = personal(PlanBlock((T19,), 3))

    assert TurnCall.of(game).target == T19


def test_a_setup_leaves_the_plan_out_so_trainings_of_one_kind_compare():
    options = PersonalOptions(
        PersonalFocus.DOUBLES, PersonalLength.SHORT, (PlanBlock((D16,), 45),), (Baseline(D16, 9, 1),)
    )

    setup = GameSetup.of(GameVariant.PERSONAL, None, None, options)

    assert setup.options == PersonalOptions(PersonalFocus.DOUBLES, PersonalLength.SHORT)


def test_weak_fields_rank_against_the_ring_average_and_thin_ones_last():
    statistics = record((D20, 40, 10), (D16, 40, 2), (D8, 20, 2), (T20, 40, 4), (T19, 30, 0), (D10, 4, 0))

    ranked = weaknesses(statistics, (2, 3))

    assert [weak.target for weak in ranked] == [
        Target(19, 3), Target(16, 2), Target(8, 2), Target(20, 3), Target(20, 2), Target(10, 2)
    ]
    assert (ranked[1].ring_darts, ranked[1].ring_hits) == (104, 14)
    assert not ranked[-1].telling


D10 = (10, 2)


def test_a_double_focus_leaves_the_triples_out():
    statistics = record((D16, 40, 2), (T19, 30, 0))

    assert [weak.target for weak in weaknesses(statistics, (2,))] == [Target(16, 2)]


def test_the_plan_trains_the_three_weakest_and_keeps_their_records():
    statistics = record((D20, 40, 10), (D16, 40, 2), (D8, 20, 2), (T20, 40, 4), (T19, 30, 0))

    plan = build_plan(statistics, PersonalFocus.ALL, PersonalLength.MEDIUM)

    assert [block.fields for block in plan.options.blocks] == [(T19,), (D16,), (D8,), (T19, D16, D8)]
    assert plan.options.baselines == (Baseline(T19, 30, 0), Baseline(D16, 40, 2), Baseline(D8, 20, 2))
    assert (plan.games, plan.darts) == (1, 170)


def test_without_a_record_the_plan_probes_the_most_played_fields():
    plan = build_plan(TargetStatistics(), PersonalFocus.DOUBLES, PersonalLength.SHORT)

    assert [block.fields for block in plan.options.blocks[:3]] == [(D20,), (D16,), (D8,)]
    assert not any(weak.telling for weak in plan.fields)
    assert plan.options.baselines == (Baseline(D20, 0, 0), Baseline(D16, 0, 0), Baseline(D8, 0, 0))


def test_a_thin_record_fills_up_after_the_telling_fields():
    statistics = record((D8, 20, 1), (D20, 3, 1))

    plan = build_plan(statistics, PersonalFocus.DOUBLES, PersonalLength.SHORT)

    assert [weak.target for weak in plan.fields] == [Target(8, 2), Target(20, 2), Target(16, 2)]
    assert plan.options.baselines[1] == Baseline(D20, 3, 1)


S20, S19 = (20, 1), (19, 1)


def test_a_single_is_hit_by_every_ring_of_its_number():
    game = personal(PlanBlock((S20,), 6))

    play(game, "T20 D20 20", "5 0 25")

    player = game.progress.players[0]
    assert (player.darts, player.hits) == (6, 3)
    assert game.targets()[0][0] == Target(20, None)


def test_the_single_pools_its_own_ring_and_every_ring_of_the_number():
    statistics = TargetStatistics()
    shots = [(Target(20, 1), Dart(20, 1)), (Target(20, 1), Dart(5, 1)), (Target(20, None), Dart(20, 3))]
    shots += [(Target(20, None), Dart(1, 1))] * 2
    statistics.add_game("game", datetime(2026, 11, 1), [AimedDart(*shot) for shot in shots], False)

    (single,) = weaknesses(statistics, (None,))

    assert (single.target, single.darts, single.hits) == (Target(20, None), 5, 2)


def test_a_single_focus_probes_the_singles_and_mixed_takes_them_too():
    singles = build_plan(TargetStatistics(), PersonalFocus.SINGLES, PersonalLength.SHORT)
    statistics = record((D16, 20, 10), (D8, 20, 10))
    shots = [(19, 2, Dart(19, 1)), (19, 18, Dart(0, 0)), (20, 18, Dart(20, 1)), (20, 2, Dart(0, 0))]
    darts = [AimedDart(Target(value, None), dart) for value, count, dart in shots for _ in range(count)]
    statistics.add_game("clock", datetime(2026, 11, 2), darts, False)
    mixed = build_plan(statistics, PersonalFocus.ALL, PersonalLength.SHORT)

    assert [block.fields for block in singles.options.blocks[:3]] == [(S20,), (S19,), ((18, 1),)]
    assert mixed.options.baselines[0] == Baseline(S19, 20, 2)


def test_without_any_ring_only_the_single_hits_a_planned_single():
    options = PersonalOptions(PersonalFocus.SINGLES, any_ring=False, blocks=(PlanBlock((S20,), 3),))
    game = new_game(1, variant=GameVariant.PERSONAL, options=options)

    play(game, "T20 D20 20")

    assert game.progress.players[0].hits == 1
    assert game.targets()[0][0] == Target(20, 1)
