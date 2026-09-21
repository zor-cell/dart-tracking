"""Measure tracking accuracy over the games played, from their event logs.

Compares what the camera booked against what the players signed off on, per
visit, by sequence alignment - so one missed dart reads as one missed dart and
not as the two or three corrections it cost (docs/feature/auswertung.md §3).

Usage:
    uv run python scripts/evaluation/report.py                       # finished games, as the page
    uv run python scripts/evaluation/report.py --test-runs-only
    uv run python scripts/evaluation/report.py --include-unfinished
    uv run python scripts/evaluation/report.py <game-id> ...
    uv run python scripts/evaluation/report.py --out results/evening-1

Writes `accuracy.md` to `testdata/evaluation/_report` and, into each game's frame
folder, the `ground_truth.txt` the offline runner reads - so a corrected visit
becomes a test case without being labelled by hand.
"""

import argparse
import asyncio
import math
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.domain.camera_angle import CameraAngle  # noqa: E402
from app.api.features.evaluation.domain.accuracy import (  # noqa: E402
    Accuracy,
    JudgedGame,
    Judgement,
    summarise,
)
from app.api.features.evaluation.domain.alignment import (  # noqa: E402
    DartOutcome,
    align,
)
from app.api.features.evaluation.domain.visit_replay import Visit  # noqa: E402
from app.api.features.evaluation.services.accuracy import judged_games  # noqa: E402
from app.api.features.evaluation.services.frame_buffer import (  # noqa: E402
    FrameKind,
    folder_of,
    read_manifest,
    series_name,
)
from app.infrastructure import database  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402

from scripts.common import rate_table, write_markdown  # noqa: E402
from scripts.evaluation.selection import add_selection_arguments  # noqa: E402

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

# Radius of the board itself, in mm. A booked MISS beyond it lies off the board.
BOARD_EDGE_MM = 225.0

# Upper edges of the camera tilt bands, in degrees.
TILT_BANDS = (20, 35, 50)
# A horizontal or vertical angle within this many degrees counts as level with the bull.
LEVEL_DEG = 15.0


def series_labels(folder: Path, visit: Visit) -> list[str] | None:
    """Truth lines for one visit's frames, or None if they do not match the
    booked darts. Absorbed frames read NO_CHANGE, unbooked ones stay unlabelled."""
    series = series_name(visit.turn_index)
    frames = len(list(folder.glob(f"{series}_dart*.jpg")))
    # Series written before manifests existed hold booked darts only.
    kinds = read_manifest(folder, series) or [FrameKind.BOOKED] * frames
    if len(kinds) != frames or kinds.count(FrameKind.BOOKED) != len(visit.claimed):
        return None

    tracked = [event.label for event in visit.claimed]
    expected = [event.label for event in visit.accepted]
    booked = iter(
        expected[right] if right is not None else NO_CHANGE_LABEL
        for left, right in align(tracked, expected)
        if left is not None
    )

    lines = []
    for index, kind in enumerate(kinds, start=1):
        if kind is FrameKind.BOOKED:
            lines.append(f"{series}_dart{index} {next(booked)}")
        elif kind is FrameKind.ABSORBED:
            lines.append(f"{series}_dart{index} {NO_CHANGE_LABEL}")
    return lines


def write_ground_truth(game_id: str, visits: list[Visit]) -> Path | None:
    """Label the frames kept for this game, in the offline runner's format."""
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
        labels = series_labels(folder, visit)
        if labels is None:
            print(f"  ! {folder.name}/{series}: frames do not match the booked darts, left unlabelled")
            continue
        lines += labels

    path = folder / GROUND_TRUTH_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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


def miss_table(judgements: list[Judgement]) -> list[str]:
    """Booked MISS darts by where their tip landed. A correct one off the board
    may be a phantom that happened to meet a zero entered by hand."""
    booked = [
        j for j in judgements
        if j.tracked is not None and j.tracked.label == "MISS" and j.tracked.position
    ]
    if not booked:
        return ["No MISS was booked."]

    def band(judgement: Judgement) -> str:
        on_board = math.hypot(*judgement.tracked.position) <= BOARD_EDGE_MM
        return "on the board" if on_board else f"beyond {BOARD_EDGE_MM:.0f} mm"

    counts = Counter((band(j), j.outcome) for j in booked)
    lines = ["| tip | correct | wrong | phantom |", "|---|---|---|---|"]
    for name in ("on the board", f"beyond {BOARD_EDGE_MM:.0f} mm"):
        lines.append(
            f"| {name} | {counts[name, DartOutcome.CORRECT]} "
            f"| {counts[name, DartOutcome.WRONG]} | {counts[name, DartOutcome.PHANTOM]} |"
        )
    return lines


def version_of(game: JudgedGame) -> str:
    version = game.game.tracker_version
    return "unknown" if version is None else str(version)


def tilt_band(angle: CameraAngle) -> str:
    """Overall tilt off the board normal, in bands of TILT_BANDS."""
    low = 0
    for high in TILT_BANDS:
        if angle.tilt < high:
            return f"{low} - {high}°"
        low = high
    return f">= {low}°"


def side_of(degrees: float, negative: str, positive: str) -> str:
    if degrees < -LEVEL_DEG:
        return negative
    return positive if degrees > LEVEL_DEG else f"within ±{LEVEL_DEG:.0f}°"


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


def grouped_table(
    games: list[JudgedGame], key: Callable[[JudgedGame], str | None], header: str
) -> list[str]:
    """Darts thrown and correct per group of games; games `key` cannot place are left out."""
    by_game = {game.game.id: key(game) for game in games}
    thrown = [
        j
        for game in games
        for j in game.judgements
        if j.outcome is not DartOutcome.PHANTOM and by_game[game.game.id] is not None
    ]
    if not thrown:
        return ["No game carries this yet."]
    return rate_table(
        thrown,
        lambda j: by_game[j.game_id],
        lambda j: j.outcome is DartOutcome.CORRECT,
        header,
        "correct",
    )


def camera_key(pick: Callable[[CameraAngle], str]) -> Callable[[JudgedGame], str | None]:
    return lambda game: None if game.camera is None else pick(game.camera)


def failure_table(failures: Counter) -> list[str]:
    if not failures:
        return ["None."]
    lines = ["| failure | count |", "|---|---|"]
    return lines + [f"| {name} | {count} |" for name, count in failures.most_common()]


def build_report(
    accuracy: Accuracy,
    games: list[JudgedGame],
    judgements: list[Judgement],
    failures: Counter,
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
        *game_table(games),
        "",
        "## Per tracker version",
        "",
        *grouped_table(games, version_of, "version"),
        "",
        "## Per camera angle",
        "",
        "Median over the scoring camera's calibrations in each game "
        "(docs/feature/auswertung.md §8).",
        "",
        *grouped_table(games, camera_key(tilt_band), "tilt"),
        "",
        *grouped_table(
            games,
            camera_key(lambda a: side_of(a.horizontal, "left", "right")),
            "horizontal",
        ),
        "",
        *grouped_table(
            games,
            camera_key(lambda a: side_of(a.vertical, "below", "above")),
            "vertical",
        ),
        "",
        "## Per blob cohesion",
        "",
        *cohesion_table(judgements),
        "",
        "## Booked MISS darts",
        "",
        *miss_table(judgements),
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
    game_ids: list[str] | None, test_runs_only: bool, include_unfinished: bool
) -> list[JudgedGame]:
    """The games asked for, selected exactly as the evaluation page selects them."""
    database.init(get_settings().database_url)
    try:
        async with database.session_scope() as session:
            return await judged_games(
                session,
                game_ids=game_ids,
                test_runs_only=test_runs_only,
                include_unfinished=include_unfinished,
            )
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games", nargs="*", help="game ids; default is every finished game")
    add_selection_arguments(parser)
    parser.add_argument(
        "--out", type=Path, default=REPORT_DIR, help="where accuracy.md goes"
    )
    args = parser.parse_args()

    games = asyncio.run(
        gather(args.games or None, args.test_runs_only, args.include_unfinished)
    )
    if not games:
        print("no judged darts in the selected games - was a camera scoring?")
        return 1

    all_visits: list[Visit] = []
    judgements: list[Judgement] = []
    failures: Counter = Counter()

    for game in games:
        all_visits += game.visits
        judgements += game.judgements
        failures.update(event.failure for event in game.events if event.failure)

        truth = write_ground_truth(game.game.id, game.visits)
        if truth is not None:
            print(f"labelled kept frames: {truth}")

    accuracy = summarise(len(games), all_visits, judgements)
    args.out.mkdir(parents=True, exist_ok=True)
    path = write_markdown(
        args.out, REPORT_NAME, build_report(accuracy, games, judgements, failures)
    )

    print(
        f"{accuracy.games} game(s), {accuracy.darts_thrown} darts, "
        f"{accuracy.correct} correct ({100 * accuracy.accuracy:.1f}%)"
    )
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
