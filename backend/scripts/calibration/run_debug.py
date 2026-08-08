"""Render every stage of board detection for one photo as separate images.

One picture per pipeline stage, plus one per refinement pass, so a bad fit can be
traced to the stage that caused it instead of just the final overlay being off.
One photo at a time, on purpose - a whole folder would bury the run that actually
needs looking at.

Usage:
    uv run python scripts/calibration/run_debug.py testdata/calibration/center-near.jpeg
    uv run python scripts/calibration/run_debug.py path/to/photo.jpg --out debug

Images land in `_results_debug/<setup>/<image>/` unless --out says otherwise.
"""

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.domain.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector as detector  # noqa: E402
from app.api.features.calibration.debug.render import write_debug_images  # noqa: E402

from scripts.common import debug_dir, load_image  # noqa: E402

_TESTDATA = _BACKEND / "testdata" / "calibration"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="a single photo")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default: _results_debug/<setup>/<image> under the test tree)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="use the photo at full size instead of replaying it through the client's downscale/JPEG (for comparison only)",
    )
    args = parser.parse_args()

    image = load_image(args.image, args.raw)
    if image is None:
        print(f"unreadable: {args.image}")
        return 1

    out_dir = debug_dir(args.image, _TESTDATA, args.out)

    outcome = detector.detect_board(image)
    written = write_debug_images(detector.trace, outcome, out_dir)

    if isinstance(outcome, CalibrationFailure):
        print(f"FAILED at: {outcome.value}")
    else:
        print(f"OK - {len(detector.trace.passes)} refinement pass(es)")

    print(f"\n{len(written)} debug image(s) in {out_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
