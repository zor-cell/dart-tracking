"""Copy kept frames out of the bucket into `testdata/evaluation/game_<id>/`, where
the runners replay them. Without ids, every game the bucket holds."""

import argparse
import sys
from pathlib import Path

# Import app.* from src/ (as `--app-dir src` does at runtime).
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.evaluation.services.frame_store import folder_name, store  # noqa: E402

PULL_DIR = _BACKEND / "testdata" / "evaluation"


def pull(game_id: str, target: Path) -> int:
    """Write the game's files under `target`; returns how many."""
    files = store()
    folder = target / folder_name(game_id)
    names = files.names(game_id)
    for name in names:
        data = files.read(game_id, name)
        if data is not None:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return len(names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_ids", nargs="*", help="games to pull, all of them if none")
    parser.add_argument("--out", type=Path, default=PULL_DIR, help="folder to pull into")
    args = parser.parse_args()

    game_ids = args.game_ids or store().games()
    for game_id in game_ids:
        print(f"{folder_name(game_id)}: {pull(game_id, args.out)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
