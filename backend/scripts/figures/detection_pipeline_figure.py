"""Render the detection stages of one dart as a 2x4 thesis figure.

Usage:
    uv run --with matplotlib python scripts/figures/detection_pipeline_figure.py pz_setup3/throw2 dart2
"""

import argparse
import sys
from types import SimpleNamespace
from pathlib import Path

import cv2
import matplotlib
import matplotlib.patheffects as patheffects
import matplotlib.pyplot as plt
import numpy as np

# TrueType rather than Type 3, which the thesis template's PDF/A profile rejects.
matplotlib.rcParams["pdf.fonttype"] = 42

_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.debug import render as calibration_render  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.debug import render  # noqa: E402
from app.api.features.detection.domain.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402

from scripts.common import load_image  # noqa: E402
from scripts.detection.run_debug import calibrate_reference, collect_frames, resolve_series  # noqa: E402

_DEFAULT_OUT = _BACKEND.parents[1] / "thesis" / "graphics" / "figures" / "detection-pipeline.pdf"

# Crop side as a multiple of the calibration ellipse's major axis.
_CROP_FACTOR = 1.2

# Zoom crop side as a multiple of the dart's length in the image.
_ZOOM_FACTOR = 1.4

BLACK = "#1c1c1c"

# The debug captions are diagnostics; the figure caption carries the explanation.
render._caption = lambda canvas, lines: canvas


def _board_crop(image: np.ndarray, ellipse) -> np.ndarray:
    """Square crop around the ellipse, padded black where it leaves the frame."""
    (cx, cy), axes, _ = ellipse
    return _square(image, cx, cy, round(max(axes) * _CROP_FACTOR / 2))


def _square(image: np.ndarray, cx: float, cy: float, half: int) -> np.ndarray:
    """Square crop of half side `half` (px) around a centre, padded black."""
    x0, y0 = round(cx) - half, round(cy) - half
    padded = cv2.copyMakeBorder(image, half, half, half, half, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return padded[y0 + half : y0 + 3 * half, x0 + half : x0 + 3 * half]


def _dart_window(trace) -> tuple[float, float, int]:
    """Centre and half side (px) of a square around the fused dart."""
    points = np.column_stack(np.where(np.isin(trace.labels, trace.inlier_labels))[::-1])
    (x_min, y_min), (x_max, y_max) = points.min(axis=0), points.max(axis=0)
    half = round(max(x_max - x_min, y_max - y_min) * _ZOOM_FACTOR / 2)
    return (x_min + x_max) / 2, (y_min + y_max) / 2, half


def _scored(trace, dart, calibration) -> np.ndarray:
    """Aligned frame with the projected board model, the dart axis and the tip."""
    canvas = calibration_render._draw_result(SimpleNamespace(image=trace.aligned), calibration)
    tip, far_end = (tuple(round(v) for v in end) for end in dart.axis_image)
    cv2.line(canvas, tip, far_end, render._COLOUR_AXIS, 2, cv2.LINE_AA)
    cv2.drawMarker(canvas, tip, render._COLOUR_TIP, cv2.MARKER_CROSS, 18, 2, cv2.LINE_AA)
    return canvas


def _chain(folder: Path, series: str, target: str, raw: bool):
    """Run the series like the live pipeline up to `target`; return its inputs and outcome."""
    frames = collect_frames(folder, series)
    reference = load_image(frames[0][1], raw)
    calibration = calibrate_reference(reference)
    if calibration is None:
        raise SystemExit("reference calibration failed")
    board_model = calibration_render._draw_result(board_detector.trace, calibration)
    ellipse = board_detector.trace.ellipse

    empty_board = reference
    for label, path in frames[1:]:
        frame = load_image(path, raw)
        outcome = dart_detector.detect_dart(reference, frame, calibration, empty_board)
        if label == target:
            return reference, board_model, ellipse, calibration, outcome
        if dart_detector.trace.aligned is not None:
            reference = dart_detector.trace.aligned
    raise SystemExit(f"no {target} in {series}")


def render_figure(target: Path, dart: str, out: Path, raw: bool) -> None:
    resolved = resolve_series(target)
    if resolved is None:
        raise SystemExit(1)
    reference, board_model, ellipse, calibration, outcome = _chain(*resolved, dart, raw)
    if isinstance(outcome, DetectionFailure):
        raise SystemExit(f"detection failed at {outcome.value}, no figure written")
    trace = dart_detector.trace

    # A later dart is differenced against the previous throw, not the calibration frame.
    first = board_model if dart == "dart1" else reference
    cx, cy, half = _dart_window(trace)
    framed = trace.aligned.copy()
    cv2.rectangle(
        framed, (round(cx) - half, round(cy) - half), (round(cx) + half, round(cy) + half),
        (255, 255, 255), 2, cv2.LINE_AA,
    )
    stages = [
        ("Reference", first),
        ("Throw frame", framed),
        ("Alignment", render._draw_alignment(trace)),
        ("Difference", render._draw_difference(trace)),
        ("Change mask", render._draw_mask(trace)),
        ("Fragment fusion", render._draw_components(trace)),
        ("Axis and flight end", render._draw_axis(trace)),
        ("Scored tip", _scored(trace, outcome, calibration)),
    ]

    fig, axes = plt.subplots(2, 4, figsize=(6.3, 3.4))
    for index, (ax, (title, stage)) in enumerate(zip(axes.flat, stages)):
        zoomed = index >= 5
        crop = _square(stage, cx, cy, half) if zoomed else _board_crop(stage, ellipse)
        ax.imshow(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), interpolation="none")
        ax.set_axis_off()
        ax.text(
            0.5, -0.03, f"({chr(ord('a') + index)}) {title}",
            transform=ax.transAxes, ha="center", va="top", fontsize=7, color=BLACK,
        )

    tip_x, tip_y = outcome.tip_image
    axes.flat[-1].text(
        tip_x - cx + half, tip_y - cy + half - 0.08 * half, outcome.segment.label,
        ha="center", va="bottom", fontsize=7, color="white",
        path_effects=[patheffects.withStroke(linewidth=1.4, foreground="black")],
    )

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.06, wspace=0.04, hspace=0.14)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(
        f"{outcome.segment.label}, fused {trace.fragment_count} fragment(s), "
        f"camera moved {trace.alignment_shift_px:.1f} px, written to {out}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("series", type=Path, help="a throw series, e.g. pz_setup3/throw2")
    parser.add_argument("dart", help="which dart of the series: dart1, dart2 or dart3")
    parser.add_argument("out", nargs="?", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--raw", action="store_true", help="skip the client's downscale/JPEG replay")
    args = parser.parse_args()
    render_figure(args.series, args.dart, args.out, args.raw)


if __name__ == "__main__":
    main()
