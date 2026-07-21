"""Run board detection over a folder of photos and report what happened.

Development tool for tuning detection against real footage, without a browser
or a dartboard in front of you.

    uv run python scripts/check_calibration.py
    uv run python scripts/check_calibration.py path/to/images --out results

For every image it prints how far the pipeline got, and writes an annotated
copy with the detected board drawn on top so the fit can be judged by eye.

`detect_board` already reports which stage failed. This adds the measurements
behind that verdict — how much colour was found, how the ellipse came out, how
many transitions were traced — which is what the HSV bounds get tuned against.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# Import from src/ the same way `--app-dir src` does at runtime.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.api.features.calibration.entity.board_geometry import SECTOR_COUNT  # noqa: E402
from app.api.features.calibration.entity.calibration import Calibration  # noqa: E402
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector as detector  # noqa: E402
from app.api.features.calibration.services.board_overlay import build_overlay  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
OVERLAY_COLOR = (0, 255, 255)  # BGR yellow, reads against board colours
OVERLAY_SUFFIX = "_overlay.jpg"

CAPTURE_MAX_EDGE = 1280
CAPTURE_JPEG_QUALITY = 85


def as_client_would_send(image: np.ndarray) -> np.ndarray:
    """Downscale and re-encode a photo the way the browser would."""
    height, width = image.shape[:2]
    scale = CAPTURE_MAX_EDGE / max(height, width)
    if scale < 1:
        image = cv2.resize(
            image,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, CAPTURE_JPEG_QUALITY])
    if not ok:
        return image
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def measure(image: np.ndarray) -> str:
    """Numbers behind the verdict, for tuning the thresholds against.

    Read off the trace of the run that just happened rather than recomputed, so
    these describe the masks and the ellipse detection actually used. Deriving
    them separately would quietly drift out of step with the pipeline — and did,
    once the component filters landed.
    """
    height, width = image.shape[:2]
    trace = detector.trace

    combined = cv2.bitwise_or(trace.red_mask, trace.green_mask)
    ratio = int(np.count_nonzero(combined)) / (width * height)
    parts = [
        f"red/green {ratio:.2%} of frame (min {detector._MIN_COLOURED_PIXEL_RATIO:.1%})"
    ]

    # How much of that colour the two filters threw away before the fit. A high
    # share here is normal (clutter, branding); a high share with a bad fit
    # means the filters ate the ring itself.
    coloured = max(int(np.count_nonzero(combined)), 1)
    for label, dropped in (
        ("off board", trace.dropped_off_board),
        ("outside ring", trace.dropped_outer),
    ):
        if dropped is not None:
            parts.append(f"{int(np.count_nonzero(dropped)) / coloured:.0%} dropped as {label}")

    if trace.ellipse is not None:
        (cx, cy), (axis_a, axis_b), angle = trace.ellipse
        parts.append(
            f"ellipse centre=({cx:.0f},{cy:.0f}) axes=({axis_a:.0f},{axis_b:.0f}) "
            f"tilt={angle:.0f}deg fills {max(axis_a, axis_b) / max(width, height):.0%}"
        )

    if trace.passes:
        last = trace.passes[-1]
        parts.append(
            f"{len(last.transitions)}/{SECTOR_COUNT} wires, "
            f"{last.ring_colours.count(0) / len(last.ring_colours):.0%} "
            f"of ring samples colourless"
        )

    return " | ".join(parts)


def describe(image: np.ndarray) -> tuple[Calibration | None, str]:
    """Detect, and explain the outcome."""
    outcome = detector.detect_board(image)
    detail = measure(image)

    if isinstance(outcome, CalibrationFailure):
        return None, f"{outcome.value} - {detail}"
    return outcome, detail


def annotate(image: np.ndarray, calibration) -> np.ndarray:
    """Draw the detected board over a copy of the frame."""
    canvas = image.copy()
    height, width = image.shape[:2]

    for line in build_overlay(calibration):
        points = np.array([[p[0] * width, p[1] * height] for p in line], dtype=np.int32)
        cv2.polylines(canvas, [points], False, OVERLAY_COLOR, 1, cv2.LINE_AA)

    return canvas


def main() -> int:
    default_images = Path(__file__).resolve().parents[1] / "testdata" / "calibration"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "images", nargs="?", default=default_images, type=Path, help="folder of photos"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="where to write annotated copies"
    )
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
        print("Put your photos there, or pass a path as the first argument.")
        return 1

    paths = sorted(p for p in args.images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        print(f"no images in {args.images}")
        return 1

    out_dir = args.out or args.images / "_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous overlays first, or a photo that has since been renamed or
    # that now fails leaves its old picture behind, and the folder shows a
    # result that no longer corresponds to anything this run produced.
    for stale in out_dir.glob(f"*{OVERLAY_SUFFIX}"):
        stale.unlink()

    if not args.raw:
        print(f"replaying photos as the client sends them: max edge {CAPTURE_MAX_EDGE}px, JPEG q{CAPTURE_JPEG_QUALITY}\n")

    detected = 0
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            print(f"{path.name:<32} UNREADABLE")
            continue

        if not args.raw:
            image = as_client_would_send(image)

        calibration, reason = describe(image)
        if calibration is None:
            print(f"{path.name:<32} FAIL  {reason}")
            continue

        detected += 1
        cv2.imwrite(str(out_dir / f"{path.stem}{OVERLAY_SUFFIX}"), annotate(image, calibration))
        print(f"{path.name:<32} OK    {reason}")

    print(f"\n{detected}/{len(paths)} detected")
    if detected:
        print(f"annotated copies in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
