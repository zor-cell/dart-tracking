"""Measure tracking accuracy over the played games by aligning what the camera booked
with what the players accepted, per visit; writes `accuracy_<timestamp>.md` to
`testdata/_reports` and a `ground_truth.txt` into each game's frame folder.
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
    read_manifest,
    series_name,
)
from app.api.features.evaluation.services.frame_store import (  # noqa: E402
    FrameStore,
    folder_name,
    store,
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


def series_labels(files: FrameStore, game_id: str, names: list[str], visit: Visit) -> list[str] | None:
    """Truth lines for one visit's frames, or None if they do not match the
    booked darts. Absorbed frames read NO_CHANGE, unbooked ones stay unlabelled."""
    series = series_name(visit.turn_index)
    frames = sum(1 for name in names if name.startswith(f"{series}_dart") and name.endswith(".jpg"))
    # Series written before manifests existed hold booked darts only.
    kinds = read_manifest(files, game_id, series) or [FrameKind.BOOKED] * frames
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


def write_ground_truth(game_id: str, visits: list[Visit]) -> bool:
    """Label the frames kept for this game, in the offline runner's format."""
    files = store()
    names = files.names(game_id)
    if not names:
        return False

    lines = [
        "# Written by scripts/evaluation/report.py from the game's event log.",
        "# Labels are what the players accepted, aligned onto the frames kept.",
    ]
    for visit in visits:
        series = series_name(visit.turn_index)
        if f"{series}_base.jpg" not in names:
            continue
        labels = series_labels(files, game_id, names, visit)
        if labels is None:
            print(f"  ! {folder_name(game_id)}/{series}: frames do not match the booked darts, left unlabelled")
            continue
        lines += labels

    files.write(game_id, GROUND_TRUTH_NAME, ("\n".join(lines) + "\n").encode())
    return True


async def gather(
    game_ids: list[str] | None,
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
            args.include_unfinished,
            args.min_version,
            args.version,
        )
    )
    if not games:
        print("no judged darts in the selected games - was a camera scoring?")
        return 1

    for game in games:
        if write_ground_truth(game.game.id, game.visits):
            print(f"labelled kept frames: {folder_name(game.game.id)}/{GROUND_TRUTH_NAME}")

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
