"""Render the six calibration stages of one photo as a 2x3 thesis figure.

Usage:
    uv run --with matplotlib python scripts/figures/calibration_pipeline_figure.py testdata/calibration/pz_setup/left_near2.jpg
"""

import argparse
import sys
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

from app.api.features.calibration.debug import render  # noqa: E402
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector as detector  # noqa: E402

from scripts.common import load_image  # noqa: E402

_DEFAULT_OUT = _BACKEND.parents[1] / "thesis" / "graphics" / "figures" / "calibration-pipeline.pdf"

# Crop side as a multiple of the fitted ellipse's major axis.
_CROP_FACTOR = 1.2

BLACK = "#1c1c1c"


def _crop_origin(ellipse) -> tuple[int, int, int]:
    """Top-left corner and half side (px) of a square crop around the ellipse."""
    (cx, cy), axes, _ = ellipse
    half = round(max(axes) * _CROP_FACTOR / 2)
    return round(cx) - half, round(cy) - half, half


def _board_crop(image: np.ndarray, ellipse) -> np.ndarray:
    """The square crop around the ellipse, padded black where it leaves the frame."""
    x0, y0, half = _crop_origin(ellipse)
    padded = cv2.copyMakeBorder(image, half, half, half, half, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return padded[y0 + half : y0 + 3 * half, x0 + half : x0 + 3 * half]


def _draw_sector_labels(ax, trace) -> None:
    """Sector numbers as vector text, white with a black outline."""
    x0, y0, _ = _crop_origin(trace.ellipse)
    outline = [patheffects.withStroke(linewidth=1.4, foreground="black")]
    for text, (x, y) in render.sector_label_positions(trace, len(trace.passes) - 1):
        ax.text(
            x - x0, y - y0, text, ha="center", va="center",
            fontsize=5.5, color="white", path_effects=outline,
        )


def _stages(trace, calibration) -> list[tuple[str, np.ndarray]]:
    """The six stage images, drawn by the debug renderer; wires from the last pass."""
    last = len(trace.passes) - 1
    return [
        ("Color masks", render._draw_masks(trace)),
        ("Board components", render._draw_components(trace)),
        ("Hull and ellipse", render._draw_hull_ellipse(trace)),
        ("Ring walk", render._draw_pass(trace, last, label_projection=False)),
        ("Wire assignment", render._draw_correspondences(trace, last, draw_labels=False)),
        ("Projected board model", render._draw_result(trace, calibration)),
    ]


def render_figure(photo: Path, out: Path, raw: bool) -> None:
    image = load_image(photo, raw)
    if image is None:
        raise SystemExit(f"unreadable: {photo}")

    outcome = detector.detect_board(image)
    if isinstance(outcome, CalibrationFailure):
        raise SystemExit(f"calibration failed at {outcome.value}, no figure written")
    trace = detector.trace

    fig, axes = plt.subplots(2, 3, figsize=(6.3, 4.6))
    for index, (ax, (title, stage)) in enumerate(zip(axes.flat, _stages(trace, outcome))):
        crop = _board_crop(stage, trace.ellipse)
        ax.imshow(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), interpolation="none")
        ax.set_axis_off()
        if index == 4:
            _draw_sector_labels(ax, trace)
        ax.text(
            0.5, -0.03, f"({chr(ord('a') + index)}) {title}",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color=BLACK,
        )

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.05, wspace=0.04, hspace=0.12)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"{len(trace.passes)} refinement pass(es), written to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo", type=Path, help="a single board photo")
    parser.add_argument("out", nargs="?", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--raw", action="store_true", help="skip the client's downscale/JPEG replay")
    args = parser.parse_args()
    render_figure(args.photo, args.out, args.raw)


if __name__ == "__main__":
    main()
