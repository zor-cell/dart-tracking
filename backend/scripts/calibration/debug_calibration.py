"""Render every stage of board detection for one photo as separate images.

`detect_board` fills a `CalibrationTrace` with the intermediate state it
computes anyway (masks, fitted ellipse, ring colours, wire correspondences,
per-pass centre refinement). `write_debug_images` turns that trace into
pictures, one per stage, so a bad fit can be traced back to the stage that
actually caused it instead of just the final overlay being off. The same
function backs the `debug` flag on a live `calibration_frame` message (see
core/socket.py) — this script just points it at a photo on disk instead.

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector as detector  # noqa: E402
from app.api.features.calibration.services.board_debug_images import write_debug_images  # noqa: E402

from test_calibration import as_client_would_send  # noqa: E402


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

    outcome = detector.detect_board(image)
    written = write_debug_images(detector.trace, outcome, out_dir)

    if isinstance(outcome, CalibrationFailure):
        print(f"FAILED at: {outcome.value}")
    else:
        print(f"OK — {len(detector.trace.passes)} refinement pass(es)")

    print(f"\n{len(written)} debug image(s) in {out_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
