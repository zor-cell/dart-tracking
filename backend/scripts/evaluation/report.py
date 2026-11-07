"""Measure tracking accuracy over the games played, from their event logs.

Compares what the camera booked against what the players signed off on, per
visit, by sequence alignment - so one missed dart reads as one missed dart and
not as the two or three corrections it cost.

Usage:
    uv run python scripts/evaluation/report.py                       # finished games, as the page
    uv run python scripts/evaluation/report.py --test-runs-only
    uv run python scripts/evaluation/report.py --include-unfinished
    uv run python scripts/evaluation/report.py --min-version 42
    uv run python scripts/evaluation/report.py --version 42
    uv run python scripts/evaluation/report.py <game-id> ...
    uv run python scripts/evaluation/report.py --out results/evening-1

Writes `accuracy_<timestamp>.md` to `testdata/_reports` and, into each game's frame
folder, the `ground_truth.txt` the offline runner reads - so a corrected visit
becomes a test case without being labelled by hand.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.evaluation.domain.accuracy import JudgedGame, summarise  # noqa: E402
from app.api.features.evaluation.domain.alignment import align  # noqa: E402
from app.api.features.evaluation.domain.visit_replay import Visit  # noqa: E402
from app.api.features.evaluation.services.accuracy import judged_games  # noqa: E402
from app.api.features.evaluation.services.frame_buffer import (  # noqa: E402
    FrameKind,
    folder_of,
    read_manifest,
    series_name,
)
from app.api.features.evaluation.services.report_markdown import build_report  # noqa: E402
from app.infrastructure import database  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402

from scripts.common import write_markdown  # noqa: E402
from scripts.evaluation.selection import add_selection_arguments  # noqa: E402

REPORT_DIR = _BACKEND / "testdata" / "_reports"
GROUND_TRUTH_NAME = "ground_truth.txt"
# What a frame holding no new dart is called in the offline runner's truth files.
NO_CHANGE_LABEL = "NO_CHANGE"


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


async def gather(
    game_ids: list[str] | None,
    test_runs_only: bool,
    include_unfinished: bool,
    min_version: int | None,
    version: int | None,
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
                min_version=min_version,
                version=version,
            )
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games", nargs="*", help="game ids; default is every finished game")
    add_selection_arguments(parser)
    parser.add_argument(
        "--out", type=Path, default=REPORT_DIR, help="where the report goes"
    )
    args = parser.parse_args()

    games = asyncio.run(
        gather(
            args.games or None,
            args.test_runs_only,
            args.include_unfinished,
            args.min_version,
            args.version,
        )
    )
    if not games:
        print("no judged darts in the selected games - was a camera scoring?")
        return 1

    for game in games:
        truth = write_ground_truth(game.game.id, game.visits)
        if truth is not None:
            print(f"labelled kept frames: {truth}")

    accuracy = summarise(
        len(games),
        [visit for game in games for visit in game.visits],
        [j for game in games for j in game.judgements],
    )
    args.out.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = write_markdown(
        args.out, f"accuracy_{now:%Y%m%d-%H%M%S}.md", build_report(games, created_at=now)
    )

    print(
        f"{accuracy.games} game(s), {accuracy.darts_thrown} darts, "
        f"{accuracy.correct} correct ({100 * accuracy.accuracy:.1f}%)"
    )
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
