"""Build the CV regression dataset: the photo sets and recorded games under neutral
board names, frames as the client sends them, plus the dataset and gate manifests
the tests in `tests/cv` replay. Copy the output folder to the Pi's TESTDATA_DIR.

Usage:
    uv run python scripts/regression/build_dataset.py GAME_DIR [GAME_DIR ...]
    uv run python scripts/regression/build_dataset.py testdata/_exports/export_*/testdata/evaluation/game_*

Reads `testdata/calibration` and `testdata/detection`, writes `testdata/regression`
(wiped first) and `tests/cv/dataset.txt` / `tests/cv/gate.txt`. A setup folder
`<board>[-<variant>]_setup<n>` becomes `boards/board_<letter>/[<variant>_]setup<n>`.
"""

import argparse
import shutil
import sys
from pathlib import Path

import cv2

_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from scripts.common import CAPTURE_JPEG_QUALITY, CAPTURE_MAX_EDGE  # noqa: E402
from scripts.detection.run_all import collect_series, load_ground_truth  # noqa: E402

TESTDATA = _BACKEND / "testdata"
MANIFESTS = _BACKEND / "tests" / "cv"
# Truth labels that mark the cases the pipeline finds hardest.
HARD_LABELS = {"NO_CHANGE", "MISS", "25", "BULL"}
# Series per recorded game the gate takes, at most.
GATE_SERIES_PER_GAME = 4


def client_bytes(path: Path) -> bytes:
    """The photo as the browser would send it: at most 1280 px, JPEG q85."""
    image = cv2.imread(str(path))
    height, width = image.shape[:2]
    scale = CAPTURE_MAX_EDGE / max(height, width)
    if scale >= 1:
        return path.read_bytes()
    image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, CAPTURE_JPEG_QUALITY])[1].tobytes()


def split_setup(name: str) -> tuple[str, str, str]:
    """`pz-light_setup2` -> ("pz", "light_", "setup2"); `tz_setup` -> ("tz", "", "setup")."""
    location, _, number = name.partition("_")
    board, _, variant = location.partition("-")
    return board, f"{variant}_" if variant else "", number


def board_names(*roots: Path) -> dict[str, str]:
    boards = sorted({split_setup(d.name)[0] for root in roots for d in root.glob("*_setup*") if d.is_dir()})
    return {board: f"board_{chr(ord('a') + index)}" for index, board in enumerate(boards)}


def copy_frames(source: Path, target: Path, pattern: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob(pattern)):
        (target / path.name).write_bytes(client_bytes(path))
    truth = source / "ground_truth.txt"
    if truth.exists():
        shutil.copy(truth, target / truth.name)


def hard_series(folder: Path) -> list[str]:
    truth = load_ground_truth(folder)
    series = collect_series(folder, folder / "_results")
    hard = [
        name
        for name, frames in series.items()
        if any(truth.get(path.stem, ("",))[0] in HARD_LABELS for _, path in frames[1:])
    ]
    return hard[:GATE_SERIES_PER_GAME]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("games", nargs="+", type=Path, help="recorded game folders (game_<id>) to include")
    parser.add_argument("--out", type=Path, default=TESTDATA / "regression")
    args = parser.parse_args()

    shutil.rmtree(args.out, ignore_errors=True)
    names = board_names(TESTDATA / "calibration", TESTDATA / "detection")
    dataset: list[str] = []
    gate: list[str] = []

    for setup in sorted((TESTDATA / "calibration").glob("*_setup*")):
        board, variant, _ = split_setup(setup.name)
        target = args.out / "calibration" / names[board]
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(setup.glob("*.jpg")):
            (target / f"{variant}{path.name}").write_bytes(client_bytes(path))
    for folder in sorted((args.out / "calibration").iterdir()):
        dataset.append(folder.relative_to(args.out).as_posix())
        gate.append(dataset[-1])

    for setup in sorted((TESTDATA / "detection").glob("*_setup*")):
        board, variant, number = split_setup(setup.name)
        target = args.out / "boards" / names[board] / f"{variant}{number}"
        copy_frames(setup, target, "throw*_*.jpg")
        dataset.append(target.relative_to(args.out).as_posix())
        gate.append(f"{dataset[-1]} throw1")

    for game in sorted(args.games, key=lambda path: path.name):
        target = args.out / "games" / game.name
        copy_frames(game, target, "throw*_*.jpg")
        dataset.append(target.relative_to(args.out).as_posix())
        if hard := hard_series(target):
            gate.append(" ".join([dataset[-1], *hard]))

    header = (
        "# Written by scripts/regression/build_dataset.py.\n"
        "# A folder under $TESTDATA_DIR/regression, then the series it contributes (all if none).\n"
    )
    (MANIFESTS / "dataset.txt").write_text(header + "\n".join(dataset) + "\n")
    (MANIFESTS / "gate.txt").write_text(header + "\n".join(gate) + "\n")
    print(f"{len(dataset)} dataset folders, {len(gate)} gate entries in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
