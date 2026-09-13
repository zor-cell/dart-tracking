"""Pack logged games into a zip: their table rows as CSV and their recorded frames.

Usage:
    uv run python scripts/evaluation/export.py --list              # logged games
    uv run python scripts/evaluation/export.py                     # every test run, one zip
    uv run python scripts/evaluation/export.py <game-id> ...       # just these
    uv run python scripts/evaluation/export.py --per-game          # one zip per game
    uv run python scripts/evaluation/export.py --all-games --out /tmp

Writes to `testdata/_exports`. Inside the zip: `games.csv`, `game_events.csv`,
and `testdata/evaluation/game_<id>/` as the backend wrote it.
"""

import argparse
import asyncio
import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from sqlalchemy import Table, func, select  # noqa: E402

from app.api import tables  # noqa: E402, F401
from app.api.features.evaluation.domain.accuracy import LoggedGame  # noqa: E402
from app.api.features.evaluation.persistence.evaluation_repository import (  # noqa: E402
    repository as evaluation_repository,
)
from app.api.features.evaluation.persistence.game_event import GameEventTable  # noqa: E402
from app.api.features.evaluation.services.frame_buffer import folder_of  # noqa: E402
from app.api.features.game.persistence.game import GameTable  # noqa: E402
from app.infrastructure import database  # noqa: E402
from app.infrastructure.config import get_settings  # noqa: E402

EXPORT_DIR = _BACKEND / "testdata" / "_exports"


def _cell(value: Any) -> str:
    """One CSV cell, in the format a psql/pgAdmin export uses."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_csv(table: Table, rows: list[Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    columns = [column.name for column in table.columns]
    writer.writerow(columns)
    for row in rows:
        writer.writerow(_cell(row[name]) for name in columns)
    return buffer.getvalue()


async def _rows(session, table: Table, key, game_ids: list[str]) -> list[Any]:
    statement = select(table).where(key.in_(game_ids)).order_by(*table.primary_key.columns)
    return list((await session.execute(statement)).mappings().all())


async def list_games(evaluation_only: bool) -> list[tuple[LoggedGame, int]]:
    """Logged games with their event counts, oldest first."""
    database.init(get_settings().database_url)
    try:
        async with database.session_scope() as session:
            games = await evaluation_repository.logged_games(
                session, evaluation_only=evaluation_only
            )
            counts = dict(
                (
                    await session.execute(
                        select(GameEventTable.game_id, func.count())
                        .group_by(GameEventTable.game_id)
                    )
                ).all()
            )
            return [(game, counts.get(game.id, 0)) for game in games]
    finally:
        await database.close()


async def read_tables(game_ids: list[str]) -> tuple[str, str]:
    """The `games` and `game_events` rows of these games, as CSV text."""
    database.init(get_settings().database_url)
    try:
        async with database.session_scope() as session:
            games = await _rows(session, GameTable.__table__, GameTable.id, game_ids)
            events = await _rows(
                session, GameEventTable.__table__, GameEventTable.game_id, game_ids
            )
    finally:
        await database.close()
    return _to_csv(GameTable.__table__, games), _to_csv(GameEventTable.__table__, events)


def write_zip(path: Path, game_ids: list[str]) -> tuple[int, int]:
    """Write one export. Returns the number of games and of frame files packed."""
    games_csv, events_csv = asyncio.run(read_tables(game_ids))
    path.parent.mkdir(parents=True, exist_ok=True)
    files = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("games.csv", games_csv)
        archive.writestr("game_events.csv", events_csv)
        for game_id in game_ids:
            folder = folder_of(game_id)
            if not folder.is_dir():
                continue
            for file in sorted(folder.rglob("*")):
                relative = file.relative_to(folder)
                # `_results*` folders are local runner output, not recorded frames.
                if not file.is_file() or any(part.startswith("_") for part in relative.parts):
                    continue
                arcname = Path("testdata") / "evaluation" / folder.name / relative
                archive.write(file, arcname.as_posix())
                files += 1
    return len(game_ids), files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("games", nargs="*", help="game ids; default is every test run")
    parser.add_argument(
        "--all-games", action="store_true", help="include games not marked as a test run"
    )
    parser.add_argument("--per-game", action="store_true", help="one zip per game")
    parser.add_argument("--list", action="store_true", help="list logged games and exit")
    parser.add_argument("--out", type=Path, default=EXPORT_DIR, help="where the zips go")
    args = parser.parse_args()

    if args.list:
        for game, events in asyncio.run(list_games(evaluation_only=not args.all_games)):
            frames = folder_of(game.id)
            count = sum(1 for f in frames.glob("*.jpg")) if frames.is_dir() else 0
            test = "test run" if game.evaluation_enabled else "        "
            print(
                f"{game.id}  {game.created_at:%Y-%m-%d %H:%M}  {test}  "
                f"{events:4d} events  {count:4d} frames"
            )
        return 0

    game_ids = args.games or [
        game.id for game, _ in asyncio.run(list_games(evaluation_only=not args.all_games))
    ]
    if not game_ids:
        print("no logged games found - play one with the test run switch on")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batches = [[game_id] for game_id in game_ids] if args.per_game else [game_ids]
    for batch in batches:
        name = f"game_{batch[0]}_{stamp}.zip" if len(batch) == 1 else f"export_{stamp}.zip"
        path = args.out / name
        games, files = write_zip(path, batch)
        print(f"{path}  ({games} game(s), {files} frame file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
