from datetime import UTC, datetime

import pytest

from app.api.features.evaluation.domain.accuracy import (
    CameraAngle,
    FieldKind,
    LoggedGame,
    judge,
    summarise,
)
from app.api.features.evaluation.domain.alignment import DartOutcome, align, outcome_of
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter
from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.evaluation.domain.snapping import snapped_darts
from app.api.features.evaluation.domain.visit_replay import replay
from app.api.features.game.domain.game_mode import GameMode

K = GameEventKind


def event(kind: GameEventKind, field: tuple[int, int] | None = None, **fields) -> GameEvent:
    value, multiplier = field if field is not None else (None, None)
    return GameEvent(
        kind=kind,
        turn_index=fields.pop("turn", 0),
        player_index=fields.pop("player", 0),
        accepted=fields.pop("accepted", True),
        value=value,
        multiplier=multiplier,
        **fields,
    )


def outcomes(tracked: list[str], expected: list[str]) -> list[DartOutcome]:
    return [
        outcome_of(
            tracked[left] if left is not None else None,
            expected[right] if right is not None else None,
        )
        for left, right in align(tracked, expected)
    ]


def test_mis_score_is_one_wrong_dart():
    assert outcomes(["S20", "S1", "S5"], ["S20", "T1", "S5"]) == [
        DartOutcome.CORRECT,
        DartOutcome.WRONG,
        DartOutcome.CORRECT,
    ]


def test_missed_first_dart_does_not_shift_the_rest_into_errors():
    assert outcomes(["S1", "S18"], ["S20", "S1", "S18"]) == [
        DartOutcome.MISSED,
        DartOutcome.CORRECT,
        DartOutcome.CORRECT,
    ]


def test_phantom_dart():
    assert outcomes(["S20", "S5", "S1"], ["S20", "S1"]) == [
        DartOutcome.CORRECT,
        DartOutcome.PHANTOM,
        DartOutcome.CORRECT,
    ]


def test_replay_keeps_the_claim_that_undo_took_back():
    visits = replay(
        [
            event(K.DETECTED, (20, 1)),
            event(K.DETECTED, (5, 1)),
            event(K.UNDO),
            event(K.MANUAL, (1, 1)),
            event(K.DETECTED, (18, 1), accepted=False),
            event(K.NEXT_PLAYER, camera_armed=True),
            event(K.MANUAL, (20, 3), player=1),
        ]
    )

    first, second = visits
    assert [e.label for e in first.claimed] == ["S20", "S5"]
    assert [e.label for e in first.accepted] == ["S20", "S1"]
    assert first.corrected
    assert first.attempts == 3
    assert (second.player_index, second.camera_armed, second.tracked) == (1, True, True)


def test_replay_follows_a_reopened_visit():
    visits = replay(
        [
            event(K.DETECTED, (20, 1)),
            event(K.NEXT_PLAYER),
            event(K.VISIT_REOPENED, player=1),
            event(K.DART_REPLACED, (20, 3), dart_index=0),
            event(K.DETECTED, (1, 1)),
            event(K.DART_MOVED, dart_index=1, target_index=0),
            event(K.DART_REMOVED, dart_index=5),
        ]
    )

    [reopened] = visits
    assert [e.label for e in reopened.accepted] == ["S1", "T20"]
    assert [e.label for e in reopened.claimed] == ["S20", "S1"]


def test_replay_takes_a_dart_out_of_the_visit_a_removal_reopened():
    visits = replay(
        [
            event(K.MANUAL, (0, 0)),
            event(K.MANUAL, (0, 0)),
            event(K.MANUAL, (0, 0)),
            event(K.NEXT_PLAYER, camera_armed=True),
            event(K.VISIT_REOPENED, player=1, turn=1),
            event(K.DART_REMOVED, player=1, turn=0, dart_index=2),
            event(K.DETECTED, (20, 1)),
            event(K.NEXT_PLAYER, camera_armed=True),
            event(K.DETECTED, (19, 1), player=1, turn=1),
        ]
    )

    first, second = visits
    assert [e.label for e in first.accepted] == ["MISS", "MISS", "S20"]
    assert (second.player_index, [e.label for e in second.accepted]) == (1, ["S19"])


def test_replay_books_the_misses_a_cleared_board_filled_in():
    visits = replay(
        [
            event(K.DETECTED, (20, 3)),
            event(K.MISS_FILLED, (0, 0)),
            event(K.MISS_FILLED, (0, 0)),
            event(K.NEXT_PLAYER, camera_armed=True),
        ]
    )

    assert [e.label for e in visits[0].accepted] == ["T20", "MISS", "MISS"]
    assert [e.label for e in visits[0].claimed] == ["T20"]
    assert not visits[0].corrected


def test_legacy_undo_on_an_empty_visit_takes_the_previous_dart():
    visits = replay(
        [
            event(K.DETECTED, (20, 1)),
            event(K.NEXT_PLAYER),
            event(K.UNDO, player=1),
        ]
    )

    assert visits[0].accepted == []
    assert visits[0].corrected


def test_untouched_visit_without_camera_says_nothing_about_the_tracker():
    visits = replay([event(K.MANUAL, (20, 1)), event(K.NEXT_PLAYER)])

    assert not visits[0].tracked


def test_summary_counts_thrown_and_booked_darts_apart():
    visits = replay(
        [
            event(K.DETECTED, (20, 1), position=(0.0, 50.0)),
            event(K.DETECTED, (20, 1), position=(0.0, 150.0)),
            event(K.DART_REPLACED, (20, 3), dart_index=1),
            event(K.NEXT_PLAYER),
            event(K.DETECTED, (5, 1)),
            event(K.DART_REMOVED, dart_index=0, turn=1),
            event(K.NEXT_PLAYER),
            event(K.MANUAL, (0, 0)),
            event(K.NEXT_PLAYER, camera_armed=True),
        ]
    )
    judgements = [j for visit in visits for j in judge("game", visit)]
    accuracy = summarise(1, visits, judgements)

    assert accuracy.outcomes == {
        DartOutcome.CORRECT: 1,
        DartOutcome.WRONG: 1,
        DartOutcome.MISSED: 1,
        DartOutcome.PHANTOM: 1,
    }
    assert (accuracy.darts_thrown, accuracy.darts_booked) == (3, 3)
    assert accuracy.accuracy == 1 / 3
    assert accuracy.missed_zeros == 1
    assert accuracy.clean_visits == 0
    triple = next(field for field in accuracy.fields if field.kind is FieldKind.TRIPLE)
    assert (triple.wrong, triple.wrong_ring) == (1, 1)
    outside = next(field for field in accuracy.fields if field.kind is FieldKind.OUTSIDE)
    assert (outside.missed, outside.missed_zeros) == (1, 1)
    assert accuracy.distances == (150.0 - 107.4,)


def logged(versions: tuple[int, ...], *, mode: int = 501) -> LoggedGame:
    return LoggedGame(
        id="g",
        mode=mode,
        created_at=datetime(2026, 10, 15, tzinfo=UTC),
        tracker_versions=versions,
    )


@pytest.mark.parametrize(
    ("criteria", "game", "selected"),
    [
        (EvaluationFilter(), logged(()), True),
        (EvaluationFilter(version_from=5, version_to=5), logged((5,)), True),
        (EvaluationFilter(version_from=5, version_to=5), logged((4, 5)), False),
        (EvaluationFilter(version_from=4, version_to=6), logged((4, 5)), True),
        (EvaluationFilter(version_from=5), logged((6,)), True),
        (EvaluationFilter(version_to=5), logged(()), False),
        (EvaluationFilter(modes=(GameMode.X01_301,)), logged((5,)), False),
        (EvaluationFilter(since=datetime(2026, 10, 16, tzinfo=UTC)), logged((5,)), False),
        (EvaluationFilter(until=datetime(2026, 10, 16, tzinfo=UTC)), logged((5,)), True),
    ],
)
def test_evaluation_filter_selects_games(criteria, game, selected):
    assert criteria.selects(game) is selected


@pytest.mark.parametrize(
    ("criteria", "tilt", "selected"),
    [
        (EvaluationFilter(), None, True),
        (EvaluationFilter(tilt_from=20), None, False),
        (EvaluationFilter(tilt_from=20, tilt_to=40), 30.0, True),
        (EvaluationFilter(tilt_from=20, tilt_to=40), 41.0, False),
    ],
)
def test_evaluation_filter_reads_the_camera_tilt(criteria, tilt, selected):
    camera = None if tilt is None else CameraAngle(tilt=tilt, horizontal=0, vertical=0, focal_px=1)
    assert criteria.selects_camera(camera) is selected


@pytest.mark.parametrize(("tip", "kept"), [((0.0, 158.5), True), ((0.0, 150.0), False)])
def test_an_old_correction_keeps_a_tip_on_the_edge_of_its_field(tip, kept):
    log = [
        event(K.DETECTED, (20, 1), position=tip),
        event(K.DART_REPLACED, (20, 2), dart_index=0),
        event(K.NEXT_PLAYER, camera_armed=True),
    ]

    found = snapped_darts("game", log)

    assert [(snapped.turn_index, snapped.dart_index, snapped.dart.label) for snapped in found] == (
        [(0, 0, "D20")] if kept else []
    )


def test_the_distance_bands_count_the_darts_a_correction_moved_into_their_field():
    visits = replay(
        [
            event(K.DETECTED, (0, 0), position=(0.0, 171.0)),
            event(K.DART_REPLACED, (20, 2), dart_index=0),
            event(K.NEXT_PLAYER, camera_armed=True),
            event(K.DETECTED, (20, 2), position=(0.0, 169.5), turn=1),
            event(K.DART_REPLACED, (0, 0), dart_index=0, turn=1),
            event(K.NEXT_PLAYER, camera_armed=True),
            event(K.DETECTED, (20, 1), position=(0.0, 150.0), turn=2),
            event(K.DART_REPLACED, (20, 2), dart_index=0, turn=2),
            event(K.NEXT_PLAYER, camera_armed=True),
        ]
    )
    judgements = [j for visit in visits for j in judge("game", visit)]
    accuracy = summarise(1, visits, judgements)

    assert [j.snapped for j in judgements] == [True, False, False]
    assert [(band.darts, band.snapped) for band in accuracy.bands] == [(2, 1), (1, 0), (0, 0), (0, 0), (0, 0)]


def test_a_tip_on_the_edge_of_the_expected_field_counts_in_the_first_band():
    visits = replay(
        [
            event(K.DETECTED, (20, 1), position=(0.0, 165.0)),
            event(K.DART_REPLACED, (20, 2), dart_index=0),
            event(K.NEXT_PLAYER, camera_armed=True),
        ]
    )
    accuracy = summarise(1, visits, [j for visit in visits for j in judge("game", visit)])

    assert [(band.darts, band.snapped) for band in accuracy.bands][0] == (1, 1)


def test_a_correction_in_a_closed_visit_lands_in_that_visit():
    visits = replay(
        [
            event(K.DETECTED, (20, 1)),
            event(K.DETECTED, (5, 1)),
            event(K.DETECTED, (1, 1)),
            event(K.NEXT_PLAYER),
            event(K.DETECTED, (19, 1), turn=1, player=1),
            event(K.DART_REPLACED, (20, 3), dart_index=0, turn=0, player=1),
            event(K.DART_REMOVED, dart_index=1, turn=0, player=1),
            event(K.DART_REPLACED, (18, 1), dart_index=2, turn=0, player=1),
        ]
    )

    first, second = visits
    assert [(e.value, e.multiplier) for e in first.accepted] == [(20, 3), (18, 1)]
    assert [(e.value, e.multiplier) for e in first.claimed] == [(20, 1), (5, 1), (1, 1)]
    assert first.corrected and not second.corrected
    assert [(e.value, e.multiplier) for e in second.accepted] == [(19, 1)]


def test_an_uncorrected_dart_without_effect_is_left_out_as_unverified():
    no_effect = {"no_effect": 1.0}
    events = [
        event(K.DETECTED, (9, 1), metrics=no_effect),
        event(K.DETECTED, (12, 1), metrics=no_effect),
        event(K.DART_REPLACED, (20, 1), dart_index=1),
        event(K.DETECTED, (20, 3)),
    ]
    visits = replay(events)
    judgements = [j for visit in visits for j in judge("g", visit)]

    assert [j.unverified for j in judgements] == [True, False, False]
    accuracy = summarise(1, visits, judgements)
    assert (accuracy.unverified, accuracy.darts_thrown, accuracy.correct) == (1, 2, 1)
