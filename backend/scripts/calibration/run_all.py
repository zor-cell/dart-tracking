"""Run board detection over a folder of photos and report what happened.

For tuning detection against real footage, without a browser or a dartboard in
front of you. Prints how far the pipeline got per image and writes an annotated
copy with the board drawn on, plus `_results/results.md`: detection rate per
board, the stage failures gave up at, and the colour signal the HSV bounds get
tuned against.

Usage:
    uv run python scripts/calibration/run_all.py
    uv run python scripts/calibration/run_all.py path/to/images --out results
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.entity.board_geometry import SECTOR_COUNT  # noqa: E402
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector as detector  # noqa: E402
from app.api.features.calibration.services.board_overlay import build_overlay  # noqa: E402

from scripts.common import (  # noqa: E402
    CAPTURE_JPEG_QUALITY,
    CAPTURE_MAX_EDGE,
    clear_results,
    collect_images,
    count_table,
    load_image,
    location_of,
    mirrored_dir,
    rate_table,
    write_markdown,
)

OVERLAY_COLOR = (0, 255, 255)  # BGR yellow, reads against board colours
OVERLAY_SUFFIX = "_overlay.jpg"
REPORT_NAME = "results.md"


@dataclass
class Result:
    """One board-detection attempt over a test photo, and what it measured."""

    key: str  # path relative to the test root, e.g. "pz_setup/center-near.jpeg"
    detected: bool
    failure: str | None  # CalibrationFailure.value, or "unreadable"
    colour_ratio: float | None  # red/green share of the frame
    wires: int | None  # colour transitions in the last pass (target: SECTOR_COUNT)
    colourless: float | None  # share of ring samples that returned no colour


def measure(image: np.ndarray) -> str:
    """Numbers behind the verdict, for tuning the thresholds against.

    Read off the trace of the run that just happened, never recomputed: deriving
    them separately drifts out of step with the pipeline — and did, once the
    component filters landed.
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


def metrics() -> tuple[float | None, int | None, float | None]:
    """The report figures — colour ratio, wires found, colourless ring share.

    Read off the trace, for the same reason `measure` is.
    """
    trace = detector.trace
    if trace.red_mask is None or trace.green_mask is None:
        return None, None, None

    combined = cv2.bitwise_or(trace.red_mask, trace.green_mask)
    height, width = trace.red_mask.shape[:2]
    ratio = int(np.count_nonzero(combined)) / (width * height)

    wires = colourless = None
    if trace.passes:
        last = trace.passes[-1]
        wires = len(last.transitions)
        if last.ring_colours:
            colourless = last.ring_colours.count(0) / len(last.ring_colours)
    return ratio, wires, colourless


def annotate(image: np.ndarray, calibration) -> np.ndarray:
    """Draw the detected board over a copy of the frame."""
    canvas = image.copy()
    height, width = image.shape[:2]

    for line in build_overlay(calibration):
        points = np.array([[p[0] * width, p[1] * height] for p in line], dtype=np.int32)
        cv2.polylines(canvas, [points], False, OVERLAY_COLOR, 1, cv2.LINE_AA)

    return canvas


def write_report(results: list[Result], out_dir: Path) -> Path:
    """Write a Markdown summary: detection rate per board, failures, signal.

    No ground-truth camera pose exists to score the homography against, so unlike
    detection this reports how often the board was found and where it broke, not
    accuracy.
    """
    detected = [r for r in results if r.detected]
    lines = [
        "# Calibration results",
        "",
        "Board detection over the test photos, each replayed through the client's",
        "downscale + JPEG. *Detected* means the pipeline produced a homography;",
        "there is no ground-truth pose to score against, so the figures are the",
        "detection rate, the stage failures gave up at, and the colour signal.",
        "",
        f"- Photos: **{len(results)}**",
        f"- Detected: **{len(detected)}/{len(results)}** ({100 * len(detected) / len(results):.0f}%)",
        "",
        "## Per location (board)",
        "",
    ]
    lines += rate_table(results, lambda r: location_of(r.key), lambda r: r.detected, "location", "detected")

    failures = [r for r in results if not r.detected]
    lines += ["", f"## Failures by stage ({len(failures)})", ""]
    if failures:
        lines += count_table(failures, lambda r: r.failure or "unknown", "stage")
    else:
        lines.append("None — every photo calibrated.")

    measured = [r for r in results if r.colour_ratio is not None]
    reached_ring = [r for r in measured if r.colourless is not None]
    lines += ["", "## Signal", ""]
    if measured:
        mean_ratio = sum(r.colour_ratio for r in measured) / len(measured)
        full = sum(1 for r in measured if r.wires == SECTOR_COUNT)
        lines.append(f"- Mean red/green coverage: **{mean_ratio:.2%}** of frame")
        lines.append(f"- Photos with all {SECTOR_COUNT} sector wires: **{full}/{len(measured)}**")
        if reached_ring:
            mean_colourless = sum(r.colourless for r in reached_ring) / len(reached_ring)
            lines.append(
                f"- Mean colourless ring samples: **{mean_colourless:.0%}** "
                f"(over {len(reached_ring)} photo(s) that reached the ring walk)"
            )
    else:
        lines.append("No photo produced a colour mask.")
    lines.append("")

    return write_markdown(out_dir, REPORT_NAME, lines)


def main() -> int:
    default_images = _BACKEND / "testdata" / "calibration"

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
        "client's downscale and JPEG compression (for comparison only - the "
        "default reflects what detection actually receives)",
    )
    args = parser.parse_args()

    if not args.images.is_dir():
        print(f"no such folder: {args.images}")
        print("Put your photos there, or pass a path as the first argument.")
        return 1

    out_dir = args.out or args.images / "_results"
    paths = collect_images(args.images, out_dir)
    if not paths:
        print(f"no images in {args.images}")
        return 1

    clear_results(out_dir, args.images)

    if not args.raw:
        print(f"replaying photos as the client sends them: max edge {CAPTURE_MAX_EDGE}px, JPEG q{CAPTURE_JPEG_QUALITY}\n")

    results: list[Result] = []
    for path in paths:
        label = path.relative_to(args.images).as_posix()
        image = load_image(path, args.raw)
        if image is None:
            print(f"{label:<40} UNREADABLE")
            results.append(Result(label, False, "unreadable", None, None, None))
            continue

        outcome = detector.detect_board(image)
        detail = measure(image)
        colour_ratio, wires, colourless = metrics()
        detected = not isinstance(outcome, CalibrationFailure)
        results.append(
            Result(
                label,
                detected,
                None if detected else outcome.value,
                colour_ratio,
                wires,
                colourless,
            )
        )

        if not detected:
            print(f"{label:<40} FAIL  {outcome.value} - {detail}")
            continue

        target = mirrored_dir(path, args.images, out_dir)
        cv2.imwrite(str(target / f"{path.stem}{OVERLAY_SUFFIX}"), annotate(image, outcome))
        print(f"{label:<40} OK    {detail}")

    detected_count = sum(r.detected for r in results)
    print(f"\n{detected_count}/{len(results)} detected")
    print(f"report: {write_report(results, out_dir)}")
    if detected_count:
        print(f"annotated copies in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
