"""Measure tracking accuracy over the games played, from their event logs.

Compares what the camera booked against what the players signed off on, per
visit, by sequence alignment - so one missed dart reads as one missed dart and
not as the two or three corrections it cost (docs/feature/auswertung.md §3).

Usage:
    uv run python scripts/evaluation/report.py                # every test run
    uv run python scripts/evaluation/report.py --all-games    # every logged game
    uv run python scripts/evaluation/report.py <game-id> ...
    uv run python scripts/evaluation/report.py --out results/evening-1

Writes `accuracy.md` to `testdata/evaluation/_report` and, into each game's frame
folder, the `ground_truth.txt` the offline runner reads - so a corrected visit
becomes a test case without being labelled by hand.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.evaluation.domain.accuracy import (  # noqa: E402
    Accuracy,
    Judgement,
    judge,
    summarise,
)
from app.api.features.evaluation.domain.alignment import (  # noqa: E402
    DartOutcome,
    align,
)
from app.api.features.evaluation.domain.game_event import GameEvent  # noqa: E402
from app.api.features.evaluation.domain.visit_replay import Visit, replay  # noqa: E402
from app.api.features.evaluation.persistence.evaluation_repository import (  # noqa: E402
    repository as evaluation_repository,
)
from app.api.features.evaluation.services.frame_buffer import (  # noqa: E402
    folder_of,
    series_name,
)
from app.infrastructure import database  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402

from scripts.common import rate_table, write_markdown  # noqa: E402

# Not `_results`: that is where `run_all.py` writes when pointed at this tree,
# and it wipes the folder before each run.
REPORT_DIR = _BACKEND / "testdata" / "evaluation" / "_report"
REPORT_NAME = "accuracy.md"
GROUND_TRUTH_NAME = "ground_truth.txt"
# What a frame holding no new dart is called in the offline runner's truth files.
NO_CHANGE_LABEL = "NO_CHANGE"

# A mismatch closer than this to the expected segment is a wire's-width miss
# rather than a structural failure - the same cut the offline runner makes.
NEAR_MISS_MM = 5.0

def write_ground_truth(game_id: str, visits: list[Visit]) -> Path | None:
    """Label the frames kept for this game, in the offline runner's format.

    Only a booked dart left a frame behind. A frame the alignment matched to no
    accepted dart is a phantom: nothing new is in it, so the label is NO_CHANGE.
    """
    folder = folder_of(game_id)
    if not folder.is_dir():
        return None

    lines = [
        "# Written by scripts/evaluation/report.py from the game's event log.",
        "# Labels are what the players accepted, aligned onto the frames kept.",
    ]
    for visit in visits:
        series = series_name(visit.turn_index)
        if not (folder / f"{series}_base.jpg").exists():
            continue
        tracked = [event.label for event in visit.claimed]
        expected = [event.label for event in visit.accepted]
        frame = 0
        for left, right in align(tracked, expected):
            if left is None:
                continue
            frame += 1
            lines.append(
                f"{series}_dart{frame} "
                f"{expected[right] if right is not None else NO_CHANGE_LABEL}"
            )

    path = folder / GROUND_TRUTH_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def error_table(accuracy: Accuracy) -> list[str]:
    """Counts and shares per outcome, over every judged dart."""
    total = max(sum(accuracy.outcomes.values()), 1)
    lines = ["| outcome | darts | share |", "|---|---|---|"]
    for outcome, count in accuracy.outcomes.items():
        lines.append(f"| {outcome.value} | {count} | {100 * count / total:.1f}% |")
    return lines


def distance_table(accuracy: Accuracy) -> list[str]:
    """How far the mis-scored darts landed from where they belonged: a few
    millimetres is the wrong side of a wire, tens of millimetres a fit that
    anchored on something else."""
    if not accuracy.distances:
        return ["No mis-scored dart carried a located tip."]

    lines = ["| off by | darts |", "|---|---|"]
    lines += [f"| {band.label} | {band.darts} |" for band in accuracy.bands]
    return lines + [
        "",
        f"Mean {accuracy.mean_off_by:.1f} mm, median "
        f"{accuracy.median_off_by:.1f} mm, worst {accuracy.worst_off_by:.1f} mm.",
    ]


def mismatch_table(judgements: list[Judgement]) -> list[str]:
    """Every dart the tracker got wrong, nearest first."""
    wrong = [j for j in judgements if j.outcome is not DartOutcome.CORRECT]
    if not wrong:
        return ["No mismatches."]

    wrong.sort(key=lambda j: (j.off_by_mm is None, j.off_by_mm or 0.0))
    near = sum(1 for j in wrong if j.off_by_mm is not None and j.off_by_mm <= NEAR_MISS_MM)

    lines = [
        f"{near} of {len(wrong)} mismatches are within {NEAR_MISS_MM:.0f} mm of the "
        "expected segment.",
        "",
        "| throw | tracked | expected | outcome | off by | fragments |",
        "|---|---|---|---|---|---|",
    ]
    for judgement in wrong:
        off_by = "-" if judgement.off_by_mm is None else f"{judgement.off_by_mm:.1f} mm"
        lines.append(
            f"| {judgement.key} "
            f"| {judgement.tracked.label if judgement.tracked else '-'} "
            f"| {judgement.expected_label or '-'} "
            f"| {judgement.outcome.value} "
            f"| {off_by} "
            f"| {judgement.fragments if judgement.fragments is not None else '-'} |"
        )
    return lines


def cohesion_table(judgements: list[Judgement]) -> list[str]:
    """Correctness against how many fragments the dart had to be fused from -
    the live counterpart of the offline runner's cohesion table."""
    located = [j for j in judgements if j.fragments is not None]
    if not located:
        return ["No detector metrics recorded."]

    def bucket(judgement: Judgement) -> str:
        count = judgement.fragments or 0
        if count <= 1:
            return "1 component"
        return "2 components" if count == 2 else "3+ components"

    return rate_table(
        located, bucket, lambda j: j.outcome is DartOutcome.CORRECT, "blob", "correct"
    )


def failure_table(failures: Counter) -> list[str]:
    if not failures:
        return ["None."]
    lines = ["| failure | count |", "|---|---|"]
    return lines + [f"| {name} | {count} |" for name, count in failures.most_common()]


def build_report(
    accuracy: Accuracy, judgements: list[Judgement], failures: Counter
) -> list[str]:
    return [
        "# Tracking accuracy",
        "",
        "What the camera booked against what the players accepted, aligned per",
        "visit (docs/feature/auswertung.md). *Correct* is a dart booked in the",
        "right segment; *missed* is a dart thrown that the camera never booked -",
        "a detection that came back empty included, since nothing was scored.",
        "*Phantom* is one it booked with no dart behind it.",
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
        "## Distance from the expected segment",
        "",
        *distance_table(accuracy),
        "",
        "## Per game",
        "",
        # Phantoms are left out so the denominator is the darts thrown, as in
        # the headline rate above.
        *rate_table(
            [j for j in judgements if j.outcome is not DartOutcome.PHANTOM],
            lambda j: j.game_id[:8],
            lambda j: j.outcome is DartOutcome.CORRECT,
            "game",
            "correct",
        ),
        "",
        "## Per blob cohesion",
        "",
        *cohesion_table(judgements),
        "",
        "## Detections that came back empty",
        "",
        *failure_table(failures),
        "",
        "## Mismatches",
        "",
        *mismatch_table(judgements),
    ]


async def gather(
    game_ids: list[str] | None, evaluation_only: bool
) -> dict[str, list[GameEvent]]:
    """Read the event logs of the games asked for."""
    database.init(get_settings().database_url)
    try:
        async with database.session_scope() as session:
            ids = game_ids or [
                game.id
                for game in await evaluation_repository.logged_games(
                    session, evaluation_only=evaluation_only
                )
            ]
            return {
                game_id: await evaluation_repository.events(session, game_id)
                for game_id in ids
            }
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games", nargs="*", help="game ids; default is every test run")
    parser.add_argument(
        "--all-games",
        action="store_true",
        help="include games that were not marked as a test run",
    )
    parser.add_argument(
        "--out", type=Path, default=REPORT_DIR, help="where accuracy.md goes"
    )
    args = parser.parse_args()

    logs = asyncio.run(gather(args.games or None, evaluation_only=not args.all_games))
    if not logs:
        print("no logged games found - play one with the test run switch on")
        return 1

    games = 0
    all_visits: list[Visit] = []
    judgements: list[Judgement] = []
    failures: Counter = Counter()

    for game_id, events in logs.items():
        visits = [visit for visit in replay(events) if visit.tracked]
        if not visits:
            continue
        games += 1
        all_visits += visits
        for visit in visits:
            judgements += judge(game_id, visit)
        for event in events:
            if event.failure:
                failures[event.failure] += 1

        truth = write_ground_truth(game_id, visits)
        if truth is not None:
            print(f"labelled kept frames: {truth}")

    if not judgements:
        print("no filmed visit in the logs - was a camera scoring?")
        return 1

    accuracy = summarise(games, all_visits, judgements)
    args.out.mkdir(parents=True, exist_ok=True)
    path = write_markdown(
        args.out, REPORT_NAME, build_report(accuracy, judgements, failures)
    )

    print(
        f"{accuracy.games} game(s), {accuracy.darts_thrown} darts, "
        f"{accuracy.correct} correct ({100 * accuracy.accuracy:.1f}%)"
    )
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
