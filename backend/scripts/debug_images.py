"""Render every stage of board detection for one photo as separate images.

`detect_board` can fill a DetectionTrace with the intermediate state it
computes anyway (masks, fitted ellipse, ring colours, wire correspondences,
per-pass centre refinement). This script is the other half: turn that trace
into pictures, one per stage, so a bad fit can be traced back to the stage
that actually caused it instead of just the final overlay being off.

Only one image at a time, on purpose: a run already produces one file per
stage, and per refinement pass on top of that, so pointing it at a whole
folder would bury the run that actually needs looking at.

    uv run python scripts/debug_images.py testdata/calibration/center-near.jpeg
    uv run python scripts/debug_images.py path/to/photo.jpg --out debug
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.api.features.tracking.entity.board_geometry import (  # noqa: E402
    SECTOR_COUNT,
    is_red_sector,
)
from app.api.features.tracking.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.tracking.entity.detection_trace import CalibrationTrace  # noqa: E402
from app.api.features.tracking.services import board_detector as detector  # noqa: E402
from app.api.features.tracking.services.board_overlay import build_overlay  # noqa: E402

from check_calibration import as_client_would_send  # noqa: E402

# BGR throughout, chosen to read against a board's own red/green/black/white.
_COLOUR_HULL = (255, 0, 255)  # magenta
_COLOUR_ELLIPSE = (0, 255, 255)  # yellow
_COLOUR_CENTRE = (255, 255, 255)  # white
_COLOUR_TRANSITION = (255, 128, 0)  # blue
_COLOUR_WIRE_RED = (0, 0, 220)
_COLOUR_WIRE_GREEN = (0, 200, 0)
_COLOUR_OVERLAY = (0, 255, 255)

_RING_DOT_RADIUS = 2
_MARKER_RADIUS = 5


def _draw_masks(trace: CalibrationTrace) -> np.ndarray:
    """Where red/green were classified — the raw material everything else builds on."""
    canvas = np.zeros_like(trace.image)
    canvas[..., 2] = trace.red_mask
    canvas[..., 1] = trace.green_mask
    return canvas


def _draw_hull_ellipse(trace: CalibrationTrace) -> np.ndarray:
    """The convex hull feeding fitEllipse, and what came out of it.

    A hull bulging out towards clutter outside the board (backboard text,
    stray coloured pixels) is the most common way the ellipse — and therefore
    everything downstream — comes out skewed.
    """
    canvas = trace.image.copy()
    if trace.hull is not None:
        cv2.polylines(canvas, [trace.hull], True, _COLOUR_HULL, 1, cv2.LINE_AA)
    if trace.ellipse is not None:
        cv2.ellipse(canvas, trace.ellipse, _COLOUR_ELLIPSE, 1, cv2.LINE_AA)
        centre = tuple(round(c) for c in trace.ellipse[0])
        cv2.drawMarker(canvas, centre, _COLOUR_ELLIPSE, cv2.MARKER_CROSS, 12, 1)
    return canvas


def _draw_pass(trace: CalibrationTrace, index: int) -> np.ndarray:
    """One refinement pass: rays from the centre estimate, coloured by vote.

    The dot colour is what the ring walk decided at that angle (red/green/grey
    for "unclear"); the blue ticks are where a colour transition was placed.
    Comparing this against the real photo shows whether the wires the pipeline
    thinks it found actually sit on the true sector boundaries.
    """
    current = trace.passes[index]
    canvas = trace.image.copy()
    ellipse = trace.ellipse

    for step, colour in enumerate(current.ring_colours):
        parameter = 2 * 3.141592653589793 * step / len(current.ring_colours)
        x, y = detector._ellipse_point(ellipse, parameter)
        dot_colour = (
            _COLOUR_WIRE_RED
            if colour == 1
            else _COLOUR_WIRE_GREEN
            if colour == -1
            else (90, 90, 90)
        )
        cv2.circle(canvas, (round(x), round(y)), _RING_DOT_RADIUS, dot_colour, -1)

    for parameter, _ in current.transitions:
        x, y = detector._ellipse_point(ellipse, parameter)
        cv2.circle(canvas, (round(x), round(y)), _MARKER_RADIUS, _COLOUR_TRANSITION, 2)

    centre_point = (round(current.centre[0]), round(current.centre[1]))
    cv2.drawMarker(canvas, centre_point, _COLOUR_CENTRE, cv2.MARKER_CROSS, 14, 2)

    if current.projected_centre is not None:
        refined_point = (round(current.projected_centre[0]), round(current.projected_centre[1]))
        cv2.drawMarker(canvas, refined_point, _COLOUR_ELLIPSE, cv2.MARKER_DIAMOND, 14, 2)

    return canvas


def _draw_correspondences(trace: CalibrationTrace, index: int) -> np.ndarray:
    """Which wire each transition was assigned to, once a pass has a match.

    Sector 0 (the 20) is marked distinctly so a rotation that is one or two
    sectors off — colour alternation alone leaves that ambiguous — is visible
    at a glance rather than only showing up as a wrong score later.
    """
    current = trace.passes[index]
    canvas = trace.image.copy()
    if current.correspondences is None:
        return canvas

    for wire, (parameter, board_angle) in enumerate(current.correspondences):
        x, y = detector._ellipse_point(trace.ellipse, parameter)
        colour = _COLOUR_WIRE_RED if is_red_sector(wire % SECTOR_COUNT) else _COLOUR_WIRE_GREEN
        cv2.circle(canvas, (round(x), round(y)), _MARKER_RADIUS, colour, -1)
        cv2.putText(
            canvas,
            str(wire),
            (round(x) + 6, round(y)),
            cv2.FONT_HERSHEY_PLAIN,
            1.0,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def _draw_result(trace: CalibrationTrace, calibration) -> np.ndarray:
    """The final board model projected back onto the photo, same as check_calibration.py."""
    canvas = trace.image.copy()
    height, width = canvas.shape[:2]
    for line in build_overlay(calibration):
        points = np.array([[p[0] * width, p[1] * height] for p in line], dtype=np.int32)
        cv2.polylines(canvas, [points], False, _COLOUR_OVERLAY, 1, cv2.LINE_AA)
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="a single photo")
    parser.add_argument("--out", type=Path, default=None, help="output folder (default: <image>_debug next to it)")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="use the photo at full size instead of replaying it through the client's downscale/JPEG (for comparison only)",
    )
    args = parser.parse_args()

    image = cv2.imread(str(args.image))
    if image is None:
        print(f"unreadable: {args.image}")
        return 1
    if not args.raw:
        image = as_client_would_send(image)

    out_dir = args.out or args.image.with_name(f"{args.image.stem}_debug")
    out_dir.mkdir(parents=True, exist_ok=True)

    trace = CalibrationTrace()
    outcome = detector.detect_board(image, trace)

    written = []

    if trace.red_mask is not None:
        path = out_dir / "01_masks.jpg"
        cv2.imwrite(str(path), _draw_masks(trace))
        written.append(path)

    if trace.hull is not None:
        path = out_dir / "02_hull_ellipse.jpg"
        cv2.imwrite(str(path), _draw_hull_ellipse(trace))
        written.append(path)

    for index in range(len(trace.passes)):
        path = out_dir / f"03_pass{index + 1}_wires.jpg"
        cv2.imwrite(str(path), _draw_pass(trace, index))
        written.append(path)

        if trace.passes[index].correspondences is not None:
            path = out_dir / f"04_pass{index + 1}_correspondences.jpg"
            cv2.imwrite(str(path), _draw_correspondences(trace, index))
            written.append(path)

    if not isinstance(outcome, CalibrationFailure):
        path = out_dir / "05_result.jpg"
        cv2.imwrite(str(path), _draw_result(trace, outcome))
        written.append(path)
        print(f"OK — {len(trace.passes)} refinement pass(es)")
    else:
        print(f"FAILED at: {trace.failure.value}")

    print(f"\n{len(written)} debug image(s) in {out_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
