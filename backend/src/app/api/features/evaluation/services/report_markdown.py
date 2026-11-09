"""The accuracy report as Markdown: what the evaluation page shows, as one file to keep."""

from datetime import datetime

from app.api.features.evaluation.domain.accuracy import Accuracy, JudgedGame, summarise
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.domain.breakdown import (
    Breakdowns,
    GroupFigures,
    GroupKind,
    breakdowns_of,
    version_of,
)
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter

# A mismatch closer than this to the expected segment is a wire's-width miss.
NEAR_MISS_MM = 5.0

_GROUP_SECTIONS: tuple[tuple[GroupKind, str], ...] = (
    (GroupKind.VERSION, "version"),
    (GroupKind.TILT, "tilt"),
)


def error_table(accuracy: Accuracy) -> list[str]:
    """Counts and shares per outcome, over every judged dart."""
    total = max(sum(accuracy.outcomes.values()), 1)
    lines = ["| outcome | darts | share |", "|---|---|---|"]
    for outcome, count in accuracy.outcomes.items():
        lines.append(f"| {outcome.value} | {count} | {100 * count / total:.1f}% |")
    return lines + [
        "",
        f"{accuracy.missed_zeros} of the {accuracy.outcomes[DartOutcome.MISSED]} "
        "missed darts were booked as a zero by the players.",
    ]


def field_table(accuracy: Accuracy) -> list[str]:
    """Outcomes per kind of field the thrown darts belonged in."""
    lines = [
        "| field | thrown | correct | wrong | of which ring | missed | of which zero | accuracy |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for field in accuracy.fields:
        rate = f"{100 * field.correct / field.thrown:.1f}%" if field.thrown else "-"
        lines.append(
            f"| {field.kind.value} | {field.thrown} | {field.correct} | {field.wrong} "
            f"| {field.wrong_ring} | {field.missed} | {field.missed_zeros} | {rate} |"
        )
    return lines


def distance_table(accuracy: Accuracy) -> list[str]:
    """How far the mis-scored darts landed from where they belonged."""
    if not accuracy.distances:
        return ["No mis-scored dart carried a located tip."]
    lines = ["| off by | darts |", "|---|---|"]
    lines += [f"| {band.label} | {band.darts} |" for band in accuracy.bands]
    return lines + [
        "",
        f"Mean {accuracy.mean_off_by:.1f} mm, median "
        f"{accuracy.median_off_by:.1f} mm, worst {accuracy.worst_off_by:.1f} mm.",
    ]


def group_table(rows: list[GroupFigures], header: str) -> list[str]:
    """Darts thrown and booked correctly per group; phantoms are not thrown darts."""
    if not rows:
        return ["No game carries this yet."]
    lines = [f"| {header} | games | correct | thrown | rate |", "|---|---|---|---|---|"]
    return lines + [
        f"| {row.key} | {row.accuracy.games} | {row.accuracy.correct} "
        f"| {row.accuracy.darts_thrown} | {100 * row.accuracy.accuracy:.0f}% |"
        for row in rows
    ]


def game_table(games: list[JudgedGame]) -> list[str]:
    """Every game with the tracker version and camera angle it was played with."""
    lines = [
        "| game | version | tilt | horizontal | vertical | correct | total | rate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for game in games:
        thrown = [j for j in game.judgements if j.outcome is not DartOutcome.PHANTOM]
        correct = sum(1 for j in thrown if j.outcome is DartOutcome.CORRECT)
        camera = game.camera
        angles = (
            f"{camera.tilt:.0f}° | {camera.horizontal:+.0f}° | {camera.vertical:+.0f}°"
            if camera
            else "- | - | -"
        )
        rate = f"{100 * correct / len(thrown):.0f}%" if thrown else "-"
        lines.append(
            f"| {game.game.id[:8]} | {version_of(game)} | {angles} "
            f"| {correct} | {len(thrown)} | {rate} |"
        )
    return lines


def miss_table(breakdowns: Breakdowns) -> list[str]:
    if not any(band.correct + band.wrong + band.phantom for band in breakdowns.misses):
        return ["No MISS was booked."]
    lines = ["| tip | correct | wrong | phantom |", "|---|---|---|---|"]
    return lines + [
        f"| {'on the board' if band.on_board else 'beyond the board'} | {band.correct} "
        f"| {band.wrong} | {band.phantom} |"
        for band in breakdowns.misses
    ]


def failure_table(breakdowns: Breakdowns) -> list[str]:
    if not breakdowns.failures:
        return ["None."]
    lines = ["| failure | count |", "|---|---|"]
    return lines + [f"| {name} | {count} |" for name, count in breakdowns.failures]


def mismatch_table(breakdowns: Breakdowns) -> list[str]:
    wrong = breakdowns.mismatches
    if not wrong:
        return ["No mismatches."]
    near = sum(1 for j in wrong if j.off_by_mm is not None and j.off_by_mm <= NEAR_MISS_MM)
    lines = [
        f"{near} of {len(wrong)} mismatches are within {NEAR_MISS_MM:.0f} mm of the "
        "expected segment.",
        "",
        "| throw | tracked | expected | outcome | off by | fragments |",
        "|---|---|---|---|---|---|",
    ]
    for j in wrong:
        off_by = "-" if j.off_by_mm is None else f"{j.off_by_mm:.1f} mm"
        lines.append(
            f"| {j.key} | {j.tracked.label if j.tracked else '-'} | {j.expected_label or '-'} "
            f"| {j.outcome.value} | {off_by} "
            f"| {j.fragments if j.fragments is not None else '-'} |"
        )
    return lines


def selection_lines(criteria: EvaluationFilter) -> list[str]:
    """The filters the games were picked by, one bullet each; nothing when none applies."""
    def span(low: object, high: object) -> str:
        return f"{low if low is not None else '…'} to {high if high is not None else '…'}"

    lines = []
    if criteria.version_from is not None or criteria.version_to is not None:
        lines.append(f"- Tracker versions {span(criteria.version_from, criteria.version_to)}")
    if criteria.modes:
        lines.append(f"- Modes {', '.join(str(mode.value) for mode in criteria.modes)}")
    if criteria.test_run is not None:
        lines.append("- Test runs only" if criteria.test_run else "- Ordinary games only")
    if criteria.since is not None or criteria.until is not None:
        since = criteria.since.date() if criteria.since else None
        until = criteria.until.date() if criteria.until else None
        lines.append(f"- Played {span(since, until)} (end exclusive)")
    if criteria.tilt_from is not None or criteria.tilt_to is not None:
        lines.append(f"- Camera tilt {span(criteria.tilt_from, criteria.tilt_to)}°")
    return lines


def build_report(
    games: list[JudgedGame],
    criteria: EvaluationFilter = EvaluationFilter(),
    created_at: datetime | None = None,
) -> list[str]:
    accuracy = summarise(
        len(games),
        [visit for g in games for visit in g.visits],
        [j for g in games for j in g.judgements],
    )
    breakdowns = breakdowns_of(games)
    selection = selection_lines(criteria)
    groups = breakdowns.groups
    return [
        "# Tracking accuracy",
        "",
        *([f"Created {created_at:%Y-%m-%d %H:%M}.", ""] if created_at else []),
        *(["Selected games:", "", *selection, ""] if selection else []),
        "What the camera booked against what the players accepted, aligned per",
        "visit. *Correct* is a dart booked in the right segment; *missed* is a dart",
        "thrown that the camera never booked - a detection that came back empty",
        "included. *Phantom* is one it booked with no dart behind it.",
        "",
        f"- Games: **{accuracy.games}**, visits judged: **{accuracy.visits}**",
        f"- Darts thrown: **{accuracy.darts_thrown}**, booked by the camera: "
        f"**{accuracy.darts_booked}**",
        f"- Correct segment: **{accuracy.correct} / {accuracy.darts_thrown} - "
        f"{100 * accuracy.accuracy:.1f}%**",
        f"- Visits accepted without a correction: **{accuracy.clean_visits} / "
        f"{accuracy.visits} - {100 * accuracy.clean_visit_rate:.1f}%**",
        "",
        "## Error breakdown",
        "",
        *error_table(accuracy),
        "",
        "## Accuracy per field",
        "",
        *field_table(accuracy),
        "",
        "## Distance from the expected segment",
        "",
        *distance_table(accuracy),
        "",
        "## Per game",
        "",
        *game_table(games),
        "",
        "## Per group",
        "",
        "The camera tilt is the median over the scoring camera's calibrations in each game.",
        "",
        *[
            line
            for kind, header in _GROUP_SECTIONS
            for line in (*group_table(groups[kind], header), "")
        ],
        "## Per blob cohesion",
        "",
        *group_table(groups[GroupKind.FRAGMENTS], "components"),
        "",
        "## Per dart in the visit",
        "",
        "A thrown dart counts by its place in the throw order, a phantom by its booking.",
        "",
        *group_table(groups[GroupKind.DART], "dart"),
        "",
        "## Booked MISS darts",
        "",
        *miss_table(breakdowns),
        "",
        "## Detections that came back empty",
        "",
        *failure_table(breakdowns),
        "",
        "## Mismatches",
        "",
        *mismatch_table(breakdowns),
    ]
