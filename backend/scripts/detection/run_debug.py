"""Render every stage of dart detection (`01_alignment` .. `05_result`) as images.

A whole visit is chained like the live pipeline (`base -> dart1 -> dart2 ->
dart3`), each dart differenced against the frame before it, one folder of stage
images per dart. Two paths instead run that single reference->frame pair.

Usage:
    uv run python scripts/detection/run_debug.py pz_setup1/throw1
    uv run python scripts/detection/run_debug.py throw1              # if unambiguous
    uv run python scripts/detection/run_debug.py REF.JPG FRAME.JPG   # single pair

The series may also be named by any of its frames (`pz_setup1/throw1_dart2.jpg`).
Images land in `_results_debug/<setup>/<series>/dartN/` unless --out says otherwise.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, both regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.entity.calibration import Calibration  # noqa: E402
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.entity.detection import Dart  # noqa: E402
from app.api.features.detection.entity.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402
from app.api.features.detection.services.detection_debug import write_debug_images  # noqa: E402

from scripts.common import IMAGE_SUFFIXES, clear_results, debug_dir, load_image  # noqa: E402

# The frame naming (`<series>_base` / `<series>_dartN`) is the batch script's
# convention; sharing it keeps the two scripts from drifting apart on what counts
# as a series.
from scripts.detection.run_all import FRAME_PATTERN, frame_order  # noqa: E402

_TESTDATA = _BACKEND / "testdata" / "detection"


def series_of(name: str) -> str:
    """The series a name belongs to: `throw1_dart2.jpg` and `throw1` both give `throw1`."""
    stem = Path(name).stem
    match = FRAME_PATTERN.match(stem)
    return match["series"] if match else stem


def find_series_folders(series: str) -> list[Path]:
    """Every folder under the test tree holding a `<series>_base.*` frame."""
    folders = []
    for path in sorted(_TESTDATA.rglob(f"{series}_base.*")):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        # Output folders under the test tree are all underscore-prefixed
        # (`_results`, `_results_debug`, `_socket_debug`) — never resolve into one.
        if any(part.startswith("_") for part in path.relative_to(_TESTDATA).parts[:-1]):
            continue
        folders.append(path.parent)
    return folders


def resolve_series(target: Path) -> tuple[Path, str] | None:
    """Turn the positional argument into (folder, series name), printing why if not.

    A folder part is resolved against the working directory first, the test tree
    second. A bare name is searched for and, if several setups have one by that
    name, listed rather than guessed at — running the wrong setup's throw1 looks
    like a perfectly normal result.
    """
    series = series_of(target.name)
    parent = target.parent

    if parent != Path("."):
        for folder in (Path.cwd() / parent, _TESTDATA / parent):
            if collect_frames(folder, series):
                return folder, series
        print(f"no '{series}' series in {parent} (looked from here and from {_TESTDATA})")
        return None

    folders = find_series_folders(series)
    if len(folders) == 1:
        return folders[0], series
    if not folders:
        print(
            f"no throw series '{series}' under {_TESTDATA} "
            "(expected <series>_base.JPG, <series>_dart1.JPG, ... next to each other)"
        )
        return None

    print(f"'{series}' is ambiguous - it exists in {len(folders)} setups:")
    for folder in folders:
        print(f"  {folder.relative_to(_TESTDATA).as_posix()}/{series}")
    print("pass one of these instead.")
    return None


def collect_frames(folder: Path, series: str) -> list[tuple[str, Path]]:
    """The frames of one series in that folder, base first then dart1, dart2, ..."""
    if not folder.is_dir():
        return []
    frames = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        match = FRAME_PATTERN.match(path.stem)
        if match and match["series"].lower() == series.lower():
            frames.append((match["frame"].lower(), path))
    frames.sort(key=lambda item: frame_order(item[0]))
    return frames


def calibrate_reference(reference: np.ndarray) -> Calibration | None:
    """Calibrate the series' reference frame, or report why it could not be."""
    calibration = board_detector.detect_board(reference)
    if isinstance(calibration, CalibrationFailure):
        print(f"reference calibration FAILED at: {calibration.value}")
        print("cannot run detection without a calibrated reference.")
        return None
    return calibration


def describe(outcome: Dart | DetectionFailure) -> str:
    """The one-line verdict for a detection: the scored segment, or where it failed."""
    if isinstance(outcome, DetectionFailure):
        return f"FAILED at: {outcome.value}"
    x, y = outcome.tip_board
    return (
        f"{outcome.segment.label} = {outcome.points}  "
        f"tip=({x:.1f},{y:.1f})mm  r={np.hypot(x, y):.1f}mm"
    )


def debug_one(
    reference: np.ndarray, frame: np.ndarray, calibration: Calibration, out_dir: Path
) -> Dart | DetectionFailure:
    """Detect one pair and dump its stage images into `out_dir`. Returns the outcome."""
    outcome = dart_detector.detect_dart(reference, frame, calibration)
    dart = None if isinstance(outcome, DetectionFailure) else outcome
    written = write_debug_images(dart_detector.trace, dart, out_dir)

    print(f"  inliers {dart_detector.trace.alignment_inliers}  {describe(outcome)}")
    print(f"  {len(written)} image(s) -> {out_dir}")
    return outcome


def run_series(folder: Path, series: str, out_dir: Path, raw: bool) -> int:
    """Debug all three darts of one visit, each into its own `<out_dir>/dartN`."""
    frames = collect_frames(folder, series)
    if len(frames) < 2:
        print(f"{series}: only {len(frames)} frame(s) in {folder}, nothing to compare")
        return 1
    if frames[0][0] != "base":
        print(f"{series}: no {series}_base.* in {folder}")
        return 1

    reference = load_image(frames[0][1], raw)
    if reference is None:
        print(f"unreadable: {frames[0][1]}")
        return 1

    calibration = calibrate_reference(reference)
    if calibration is None:
        return 1

    print(
        f"{folder.name}/{series}  reference {frames[0][1].name}  "
        f"({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)\n"
    )

    for label, path in frames[1:]:
        print(f"{label}  ({path.name})")
        frame = load_image(path, raw)
        if frame is None:
            print("  UNREADABLE")
            continue

        debug_one(reference, frame, calibration, out_dir / label)
        print()

        # Each dart is differenced against the frame before it, so the aligned
        # copy of this frame becomes the reference for the next one. Aligned, not
        # raw, or the reference drifts out of the calibration's frame.
        if dart_detector.trace.aligned is not None:
            reference = dart_detector.trace.aligned

    print(f"debug images in {out_dir}")
    return 0


def run_pair(reference_path: Path, frame_path: Path, out_dir: Path, raw: bool) -> int:
    """Debug a single reference/frame pair, all stage images flat in `out_dir`."""
    reference = load_image(reference_path, raw)
    if reference is None:
        print(f"unreadable: {reference_path}")
        return 1
    frame = load_image(frame_path, raw)
    if frame is None:
        print(f"unreadable: {frame_path}")
        return 1

    calibration = calibrate_reference(reference)
    if calibration is None:
        return 1

    print(
        f"reference {reference_path.name}  "
        f"({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)"
    )
    debug_one(reference, frame, calibration, out_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "target",
        type=Path,
        help="a throw series (e.g. throw1 or pz_setup1/throw1) - or, with FRAME "
        "given, the reference frame of a single pair",
    )
    parser.add_argument(
        "frame",
        type=Path,
        nargs="?",
        default=None,
        help="the frame to locate the dart in (single-pair mode)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default: _results_debug/<setup>/<series> under the test tree)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="use the photos at full size instead of replaying them through the "
        "client's downscale/JPEG (for comparison only)",
    )
    args = parser.parse_args()

    if args.frame is not None:
        out_dir = debug_dir(args.frame, _TESTDATA, args.out)
        if args.out is None:
            clear_results(out_dir, args.frame.parent)
        return run_pair(args.target, args.frame, out_dir, args.raw)

    resolved = resolve_series(args.target)
    if resolved is None:
        return 1

    folder, series = resolved
    # `folder/series` has no suffix, so its stem is the series name: the same
    # mirroring the single-pair mode uses, one level up from the frames.
    out_dir = debug_dir(folder / series, _TESTDATA, args.out)
    if args.out is None:
        # Wipe first, or a stage that this run no longer produces (a 05_result.jpg
        # from back when the fit still worked) is read as part of it.
        clear_results(out_dir, folder)
    return run_series(folder, series, out_dir, args.raw)


if __name__ == "__main__":
    raise SystemExit(main())
