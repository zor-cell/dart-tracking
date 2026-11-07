from datetime import UTC, datetime

from app.api.features.evaluation.domain.accuracy import JudgedGame, LoggedGame, judge
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.domain.breakdown import (
    GroupKind,
    booked_misses,
    breakdown,
    breakdowns_of,
    mismatches,
)
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter
from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.evaluation.domain.visit_replay import replay
from app.api.features.evaluation.services.report_markdown import build_report
from app.api.features.game.domain.game_mode import GameMode

K = GameEventKind


def event(kind: GameEventKind, field: tuple[int, int] | None = None, **fields) -> GameEvent:
    value, multiplier = field if field is not None else (None, None)
    return GameEvent(
        kind=kind,
        turn_index=0,
        player_index=0,
        accepted=True,
        value=value,
        multiplier=multiplier,
        **fields,
    )


def calibrated(tilt: float, horizontal: float = 0.0, vertical: float = 0.0) -> GameEvent:
    metrics = {"tilt_deg": tilt, "horizontal_deg": horizontal, "vertical_deg": vertical, "focal_px": 1}
    return event(K.CALIBRATED, metrics=metrics)


def judged(
    game_id: str,
    events: list[GameEvent],
    *,
    versions: tuple[int, ...] = (5,),
    test_run: bool = False,
) -> JudgedGame:
    visits = [visit for visit in replay(events) if visit.tracked]
    game = LoggedGame(
        id=game_id,
        mode=501,
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
        evaluation_enabled=test_run,
        tracker_versions=versions,
    )
    return JudgedGame(game, events, visits, [j for v in visits for j in judge(game_id, v)])


# One correct dart and one booked as S20 that the players changed to T20.
ONE_WRONG = [
    event(K.DETECTED, (20, 1), position=(0.0, 50.0), metrics={"fragment_count": 1}),
    event(K.DETECTED, (20, 1), position=(0.0, 150.0), metrics={"fragment_count": 3}),
    event(K.DART_REPLACED, (20, 3), dart_index=1),
    event(K.NEXT_PLAYER),
]
ALL_RIGHT = [event(K.DETECTED, (5, 1), position=(-30.0, 80.0)), event(K.NEXT_PLAYER)]


def test_breakdown_splits_the_darts_per_tracker_version():
    games = [
        judged("a", ONE_WRONG, versions=(5,)),
        judged("b", ALL_RIGHT, versions=(4,)),
        judged("c", ALL_RIGHT, versions=(5,)),
    ]

    rows = breakdown(games, GroupKind.VERSION)

    assert [
        (row.key, row.accuracy.games, row.accuracy.correct, row.accuracy.darts_thrown)
        for row in rows
    ] == [("4", 1, 1, 1), ("5", 2, 2, 3)]
    assert rows[1].accuracy.accuracy == 2 / 3
    assert rows[1].accuracy.visits == 2


def test_breakdown_keeps_each_groups_empty_detections():
    empty = event(K.DETECTED, failure="no_change")
    games = [
        judged("a", [empty, *ALL_RIGHT], versions=(4,)),
        judged("b", ALL_RIGHT, versions=(5,)),
    ]

    rows = breakdown(games, GroupKind.VERSION)

    assert [row.failures for row in rows] == [[("no_change", 1)], []]


def test_breakdown_reads_the_camera_tilt_and_leaves_games_without_one_out():
    games = [
        judged("a", [calibrated(40, horizontal=-30), *ONE_WRONG]),
        judged("b", [calibrated(10, vertical=20), *ALL_RIGHT]),
        judged("c", ALL_RIGHT),
    ]

    assert [row.key for row in breakdown(games, GroupKind.TILT)] == ["0-20", "35-50"]


def test_breakdown_by_blob_cohesion_counts_located_darts_only():
    rows = breakdown([judged("a", ONE_WRONG), judged("b", ALL_RIGHT)], GroupKind.FRAGMENTS)

    wrong = DartOutcome.WRONG
    assert [(row.key, row.accuracy.correct, row.accuracy.outcomes[wrong]) for row in rows] == [
        ("1", 1, 0),
        ("3+", 0, 1),
    ]
    assert all(row.accuracy.visits == 0 and row.failures == [] for row in rows)


def test_booked_misses_split_by_where_the_tip_landed():
    events = [
        event(K.DETECTED, (0, 0), position=(0.0, 300.0)),
        event(K.DETECTED, (0, 0), position=(0.0, 200.0)),
        event(K.NEXT_PLAYER),
    ]
    game = judged("a", events)

    on_board, beyond = booked_misses(game.judgements)

    assert (on_board.on_board, on_board.correct) == (True, 1)
    assert (beyond.on_board, beyond.correct) == (False, 1)


def test_mismatches_put_the_nearest_first_and_skip_correct_darts():
    events = [
        event(K.DETECTED, (1, 1), position=(0.0, 150.0)),
        event(K.DETECTED, (20, 1), position=(0.0, 150.0)),
        event(K.DART_REPLACED, (5, 1), dart_index=0),
        event(K.DART_REPLACED, (20, 3), dart_index=1),
        event(K.NEXT_PLAYER),
    ]

    wrong = mismatches(judged("a", events).judgements)

    assert [j.expected_label for j in wrong] == ["S5", "T20"]
    assert wrong[0].off_by_mm < wrong[1].off_by_mm
    assert all(j.outcome is DartOutcome.WRONG for j in wrong)


def test_report_names_the_selection_and_every_section():
    games = [judged("a", [calibrated(30), *ONE_WRONG], versions=(5,))]
    criteria = EvaluationFilter(version_from=5, version_to=5, modes=(GameMode.X01_501,))

    report = "\n".join(build_report(games, criteria))

    assert "- Tracker versions 5 to 5" in report
    assert "- Modes 501" in report
    assert "Correct segment: **1 / 2 - 50.0%**" in report
    for heading in ("## Per game", "## Per group", "## Per blob cohesion", "## Mismatches"):
        assert heading in report
    assert "| 20-35 | 1 | 1 | 2 | 50% |" in report


def test_breakdowns_cover_every_group_kind():
    groups = breakdowns_of([judged("a", ONE_WRONG)]).groups

    assert set(groups) == set(GroupKind)
