"""Render every stage of dart detection for one throw as separate images.

Detection is a difference of two frames, so it takes a **pair**: a reference
frame (the board before the throw) and the frame to inspect (the board after).
`detect_dart` fills a `DetectionTrace` with the intermediate state it computes
anyway (the aligned frame, the raw difference, the cleaned change mask, the
labelled components). `write_debug_images` turns that trace into pictures, one
per stage, so a wrong score can be traced back to the stage that caused it —
registration, thresholding, or the axis fit — instead of just the final overlay
being off. The same function backs the detection websocket path (see
core/socket.py); this script just points it at two photos on disk.

The reference is calibrated once; the frame is registered onto it, exactly as
the live pipeline does. One pair at a time, on purpose: a run already produces
one file per stage, so pointing it at a whole folder would bury the run that
actually needs looking at (use test_detection.py for the batch view).

    uv run python scripts/detection/debug_detection.py testdata/detection/throw0_base.JPG testdata/detection/throw0_dart1.JPG
    uv run python scripts/detection/debug_detection.py REF.JPG FRAME.JPG --out debug
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

from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.entity.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402
from app.api.features.detection.services.detection_debug import write_debug_images  # noqa: E402

from scripts.common import load_image  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("reference", type=Path, help="the board before the throw")
    parser.add_argument("frame", type=Path, help="the frame to locate the dart in")
    parser.add_argument(
        "--out", type=Path, default=None, help="output folder (default: <frame>_debug next to it)"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="use the photos at full size instead of replaying them through the "
        "client's downscale/JPEG (for comparison only)",
    )
    args = parser.parse_args()

    reference = load_image(args.reference, args.raw)
    if reference is None:
        print(f"unreadable: {args.reference}")
        return 1
    frame = load_image(args.frame, args.raw)
    if frame is None:
        print(f"unreadable: {args.frame}")
        return 1

    # The reference has to be calibrated in its own right — the frame is only
    # ever registered onto it, never calibrated separately (see dart_detector).
    calibration = board_detector.detect_board(reference)
    if isinstance(calibration, CalibrationFailure):
        print(f"reference calibration FAILED at: {calibration.value}")
        print("cannot run detection without a calibrated reference.")
        return 1

    outcome = dart_detector.detect_dart(reference, frame, calibration)

    out_dir = args.out or args.frame.with_name(f"{args.frame.stem}_debug")
    dart = None if isinstance(outcome, DetectionFailure) else outcome
    written = write_debug_images(dart_detector.trace, dart, out_dir)

    print(f"reference {args.reference.name}  ({dart_detector.trace.pixels_per_mm:.2f} px/mm)")
    print(f"alignment inliers: {dart_detector.trace.alignment_inliers}")
    if isinstance(outcome, DetectionFailure):
        print(f"FAILED at: {outcome.value}")
    else:
        x, y = outcome.tip_board
        print(
            f"{outcome.segment.label} = {outcome.points}  "
            f"tip=({x:.1f},{y:.1f})mm  r={np.hypot(x, y):.1f}mm"
        )

    print(f"\n{len(written)} debug image(s) in {out_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
