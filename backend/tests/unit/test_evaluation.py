from app.api.features.evaluation.domain.accuracy import FieldKind, judge, summarise
from app.api.features.evaluation.domain.alignment import DartOutcome, align, outcome_of
from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.evaluation.domain.visit_replay import replay

K = GameEventKind


def event(kind: GameEventKind, field: tuple[int, int] | None = None, **fields) -> GameEvent:
    value, multiplier = field if field is not None else (None, None)
    return GameEvent(
        kind=kind,
        turn_index=0,
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

    reopened, left = visits
    assert [e.label for e in reopened.accepted] == ["S1", "T20"]
    assert [e.label for e in reopened.claimed] == ["S20", "S1"]
    assert not left.tracked


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
            event(K.DART_REMOVED, dart_index=0),
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
    assert accuracy.distances == (150.0 - 107.4,)
