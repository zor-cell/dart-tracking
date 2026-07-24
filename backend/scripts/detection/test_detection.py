"""Run dart detection over folders of throw series and report what happened.

Expects photos named `<series>_base.JPG`, `<series>_dart1.JPG`, ... — the board
before the visit, then after each dart. Every consecutive pair is one detection:
`base -> dart1`, `dart1 -> dart2`, `dart2 -> dart3`, which is exactly what the
live pipeline does, since each throw is differenced against the previous frame
rather than against an empty board.

    uv run python scripts/check_detection.py
    uv run python scripts/check_detection.py path/to/images --out results

For every pair it prints the located segment and writes an annotated copy with
the dart's axis and tip drawn on, so the fit can be judged by eye. The reference
frame of each series is calibrated once; the rest are registered onto it.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

# Import from src/ the same way `--app-dir src` does at runtime.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.entity.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402
from scripts.calibration.test_calibration import as_client_would_send  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
OVERLAY_SUFFIX = "_detected.jpg"

FRAME_PATTERN = re.compile(r"^(?P<series>.+?)_(?P<frame>base|dart\d+)$", re.IGNORECASE)

COLOUR_AXIS = (255, 0, 255)  # magenta
COLOUR_TIP = (0, 255, 255)  # yellow
COLOUR_MASK = (60, 200, 60)


def frame_order(name: str) -> tuple[int, int]:
    """Sort key putting `base` first, then dart1, dart2, ... numerically."""
    return (0, 0) if name.lower() == "base" else (1, int(name[4:]))


def collect_series(folder: Path) -> dict[str, list[tuple[str, Path]]]:
    """Group the photos in `folder` into throw series, each in frame order."""
    series: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        match = FRAME_PATTERN.match(path.stem)
        if match:
            series[match["series"]].append((match["frame"], path))

    for frames in series.values():
        frames.sort(key=lambda item: frame_order(item[0]))
    return dict(sorted(series.items()))


def annotate(dart) -> np.ndarray:
    """Draw the located dart onto the frame it was found in.

    The aligned copy, not the reference: the dart is only visible in the newer
    frame, and drawing on the older one would show a marker floating over bare
    board with nothing to check it against.
    """
    canvas = dart_detector.trace.aligned.copy()
    if dart_detector.trace.change_mask is not None:
        canvas[dart_detector.trace.change_mask > 0] = COLOUR_MASK

    tip, far_end = dart.axis_image
    cv2.line(
        canvas,
        tuple(round(v) for v in tip),
        tuple(round(v) for v in far_end),
        COLOUR_AXIS,
        2,
        cv2.LINE_AA,
    )
    cv2.drawMarker(
        canvas, tuple(round(v) for v in tip), COLOUR_TIP, cv2.MARKER_CROSS, 18, 2, cv2.LINE_AA
    )
    cv2.putText(
        canvas,
        f"{dart.segment.label} = {dart.points}",
        (round(tip[0]) + 12, round(tip[1]) - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        COLOUR_TIP,
        2,
        cv2.LINE_AA,
    )
    return canvas


def run_series(name: str, frames: list[tuple[str, Path]], out_dir: Path, raw: bool) -> tuple[int, int]:
    """Detect every consecutive pair in one series. Returns (located, attempted)."""
    if len(frames) < 2:
        print(f"{name}: only {len(frames)} frame(s), nothing to compare")
        return 0, 0

    def load(path: Path) -> np.ndarray | None:
        image = cv2.imread(str(path))
        if image is None:
            return None
        return image if raw else as_client_would_send(image)

    reference = load(frames[0][1])
    if reference is None:
        print(f"{name}: reference {frames[0][1].name} unreadable")
        return 0, 0

    calibration = board_detector.detect_board(reference)
    if isinstance(calibration, CalibrationFailure):
        print(f"{name}: reference calibration failed ({calibration.value})")
        return 0, len(frames) - 1

    print(f"{name}  reference {frames[0][1].name}  ({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)")

    located = 0
    for (_, previous_path), (label, path) in zip(frames, frames[1:]):
        frame = load(path)
        if frame is None:
            print(f"  {label:<6} UNREADABLE")
            continue

        outcome = dart_detector.detect_dart(reference, frame, calibration)
        if isinstance(outcome, DetectionFailure):
            print(f"  {label:<6} FAIL  {outcome.value}  (inliers {dart_detector.trace.alignment_inliers})")
        else:
            located += 1
            x, y = outcome.tip_board
            print(
                f"  {label:<6} {outcome.segment.label:<5} = {outcome.points:<3} "
                f"tip=({x:6.1f},{y:6.1f})mm  r={np.hypot(x, y):5.1f}  "
                f"inliers {dart_detector.trace.alignment_inliers}"
            )
            cv2.imwrite(str(out_dir / f"{path.stem}{OVERLAY_SUFFIX}"), annotate(outcome))

        # Each dart is differenced against the frame before it, so the aligned
        # copy of this frame becomes the reference for the next one. Aligned,
        # not raw, or the reference drifts out of the calibration's frame.
        if dart_detector.trace.aligned is not None:
            reference = dart_detector.trace.aligned

    return located, len(frames) - 1


def main() -> int:
    default_images = Path(__file__).resolve().parents[1] / "testdata" / "detection"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "images", nargs="?", default=default_images, type=Path, help="folder of throw series"
    )
    parser.add_argument("--out", type=Path, default=None, help="where to write annotated copies")
    parser.add_argument("--series", default=None, help="only run series whose name contains this")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="use the photos at full size instead of replaying them through the "
        "client's downscale and JPEG compression (for comparison only — the "
        "default reflects what detection actually receives)",
    )
    args = parser.parse_args()

    if not args.images.is_dir():
        print(f"no such folder: {args.images}")
        return 1

    series = collect_series(args.images)
    if args.series:
        series = {k: v for k, v in series.items() if args.series in k}
    if not series:
        print(f"no throw series in {args.images} (expected <name>_base.JPG, <name>_dart1.JPG, ...)")
        return 1

    out_dir = args.out or args.images / "_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(f"*{OVERLAY_SUFFIX}"):
        stale.unlink()

    located = attempted = 0
    for name, frames in series.items():
        series_located, series_attempted = run_series(name, frames, out_dir, args.raw)
        located += series_located
        attempted += series_attempted
        print()

    print(f"{located}/{attempted} darts located")
    if located:
        print(f"annotated copies in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
