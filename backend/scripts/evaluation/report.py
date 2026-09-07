"""Measure tracking accuracy over the games played, from their event logs.

Compares what the camera booked against what the players signed off on, per
visit, by sequence alignment - so one missed dart reads as one missed dart and
not as the two or three corrections it cost (docs/feature/auswertung.md §3).

Usage:
    uv run python scripts/evaluation/report.py                # every test run
    uv run python scripts/evaluation/report.py --all-games    # every logged game
    uv run python scripts/evaluation/report.py <game-id> ...
    uv run python scripts/evaluation/report.py --out results/evening-1

Writes `accuracy.md` to `testdata/detection/_results_live` and, into each game's
frame folder, the `ground_truth.txt` the offline runner reads - so a corrected
visit becomes a test case without being labelled by hand.
"""

import argparse
import asyncio
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.domain.board_geometry import (  # noqa: E402
    Segment,
    distance_to_segment,
    segment_from_label,
)
from app.api.features.evaluation.domain.alignment import (  # noqa: E402
    DartOutcome,
    align,
    outcome_of,
)
from app.api.features.evaluation.domain.tracking_event import TrackingEvent  # noqa: E402
from app.api.features.evaluation.domain.visit_replay import Visit, replay  # noqa: E402
from app.api.features.evaluation.persistence.evaluation_repository import (  # noqa: E402
    repository as evaluation_repository,
)
from app.api.features.evaluation.services.frame_buffer import folder_of  # noqa: E402
from app.infrastructure import database  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402

from scripts.common import rate_table, write_markdown  # noqa: E402

# Beside the offline runner's `_results`, and named like it, so the two reports
# do not land in the same folder.
REPORT_DIR = _BACKEND / "testdata" / "detection" / "_results_live"
REPORT_NAME = "accuracy.md"
GROUND_TRUTH_NAME = "ground_truth.txt"

# A mismatch closer than this to the expected segment is a wire's-width miss
# rather than a structural failure - the same cut the offline runner makes.
NEAR_MISS_MM = 5.0

_DISTANCE_BUCKETS = (
    ("<= 5 mm", 5.0),
    ("5 - 20 mm", 20.0),
    ("20 - 50 mm", 50.0),
    ("> 50 mm", float("inf")),
)


@dataclass(frozen=True)
class Judgement:
    """One aligned dart: what the camera said, and what it should have said."""

    game_id: str
    turn_index: int
    position: int  # place within the visit, 1-based
    outcome: DartOutcome
    tracked: TrackingEvent | None
    expected_label: str | None

    @property
    def key(self) -> str:
        return f"{self.game_id[:8]}/turn{self.turn_index:03d}/dart{self.position}"

    @property
    def expected_segment(self) -> Segment | None:
        if self.expected_label is None:
            return None
        return segment_from_label(self.expected_label)

    @property
    def off_by_mm(self) -> float | None:
        """How far the scored tip landed from the segment it belonged in. Only
        for a booked and located dart: a missed one has no tip."""
        segment = self.expected_segment
        if self.outcome is not DartOutcome.WRONG or self.tracked is None:
            return None
        if self.tracked.position is None or segment is None:
            return None
        return distance_to_segment(*self.tracked.position, segment)

    @property
    def fragments(self) -> int | None:
        metrics = (self.tracked.metrics or {}) if self.tracked else {}
        count = metrics.get("fragment_count")
        return None if count is None else int(count)


def judge(game_id: str, visit: Visit) -> list[Judgement]:
    """Align one visit's claimed darts against the ones the players accepted."""
    tracked = [event.label for event in visit.claimed]
    expected = [event.label for event in visit.accepted]

    return [
        Judgement(
            game_id=game_id,
            turn_index=visit.turn_index,
            position=position,
            outcome=outcome_of(
                tracked[left] if left is not None else None,
                expected[right] if right is not None else None,
            ),
            tracked=visit.claimed[left] if left is not None else None,
            expected_label=expected[right] if right is not None else None,
        )
        for position, (left, right) in enumerate(align(tracked, expected), start=1)
    ]


def write_ground_truth(game_id: str, visits: list[Visit]) -> Path | None:
    """Label the frames kept for this game, in the offline runner's format.

    Only a booked dart left a frame behind; those get the settled label.
    """
    folder = folder_of(game_id)
    if not folder.is_dir():
        return None

    lines = [
        "# Written by scripts/evaluation/report.py from the game's event log.",
        "# Labels are what the players accepted, aligned onto the frames kept.",
    ]
    for visit in visits:
        series = f"turn{visit.turn_index:03d}"
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
                f"{expected[right] if right is not None else 'MISS'}"
            )

    path = folder / GROUND_TRUTH_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def error_table(judgements: list[Judgement]) -> list[str]:
    """Counts and shares per outcome, over every judged dart."""
    counts = Counter(judgement.outcome for judgement in judgements)
    total = max(len(judgements), 1)
    lines = ["| outcome | darts | share |", "|---|---|---|"]
    for outcome in DartOutcome:
        lines.append(
            f"| {outcome.value} | {counts[outcome]} "
            f"| {100 * counts[outcome] / total:.1f}% |"
        )
    return lines


def distance_table(judgements: list[Judgement]) -> list[str]:
    """How far the mis-scored darts landed from where they belonged: a few
    millimetres is the wrong side of a wire, tens of millimetres a fit that
    anchored on something else."""
    distances = [
        judgement.off_by_mm
        for judgement in judgements
        if judgement.off_by_mm is not None
    ]
    if not distances:
        return ["No mis-scored dart carried a located tip."]

    lines = ["| off by | darts |", "|---|---|"]
    low = 0.0
    for name, high in _DISTANCE_BUCKETS:
        lines.append(f"| {name} | {sum(1 for d in distances if low < d <= high)} |")
        low = high
    return lines + [
        "",
        f"Mean {statistics.fmean(distances):.1f} mm, median "
        f"{statistics.median(distances):.1f} mm, worst {max(distances):.1f} mm.",
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
    per_game: dict[str, list[Visit]], judgements: list[Judgement], failures: Counter
) -> list[str]:
    counts = Counter(judgement.outcome for judgement in judgements)
    thrown = len(judgements) - counts[DartOutcome.PHANTOM]
    booked = len(judgements) - counts[DartOutcome.MISSED]
    visits = [visit for game in per_game.values() for visit in game]
    clean = sum(1 for visit in visits if not visit.corrected)

    return [
        "# Tracking accuracy",
        "",
        "What the camera booked against what the players accepted, aligned per",
        "visit (docs/feature/auswertung.md). *Correct* is a dart booked in the",
        "right segment; *missed* is a dart thrown that the camera never booked,",
        "*phantom* one it booked with no dart behind it.",
        "",
        f"- Games: **{len(per_game)}**, visits judged: **{len(visits)}**",
        f"- Darts thrown: **{thrown}**, booked by the camera: **{booked}**",
        f"- Correct segment: **{counts[DartOutcome.CORRECT]} / {thrown} - "
        f"{100 * counts[DartOutcome.CORRECT] / max(thrown, 1):.1f}%**",
        f"- Visits accepted without a correction: **{clean} / {len(visits)} - "
        f"{100 * clean / max(len(visits), 1):.1f}%**",
        "",
        "## Error breakdown",
        "",
        *error_table(judgements),
        "",
        "## Distance from the expected segment",
        "",
        *distance_table(judgements),
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
) -> dict[str, list[TrackingEvent]]:
    """Read the event logs of the games asked for."""
    database.init(get_settings().database_url)
    try:
        async with database.session_scope() as session:
            ids = game_ids or await evaluation_repository.logged_games(
                session, evaluation_only=evaluation_only
            )
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

    per_game: dict[str, list[Visit]] = {}
    judgements: list[Judgement] = []
    failures: Counter = Counter()

    for game_id, events in logs.items():
        visits = [visit for visit in replay(events) if visit.tracked]
        if not visits:
            continue
        per_game[game_id] = visits
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

    args.out.mkdir(parents=True, exist_ok=True)
    path = write_markdown(
        args.out, REPORT_NAME, build_report(per_game, judgements, failures)
    )

    correct = sum(1 for j in judgements if j.outcome is DartOutcome.CORRECT)
    thrown = sum(1 for j in judgements if j.outcome is not DartOutcome.PHANTOM)
    print(
        f"{len(per_game)} game(s), {thrown} darts, {correct} correct "
        f"({100 * correct / max(thrown, 1):.1f}%)"
    )
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
