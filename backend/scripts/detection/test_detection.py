"""Run dart detection over folders of throw series and report what happened.

Expects photos named `<series>_base.JPG`, `<series>_dart1.JPG`, ... — the board
before the visit, then after each dart. Every consecutive pair is one detection:
`base -> dart1`, `dart1 -> dart2`, `dart2 -> dart3`, which is exactly what the
live pipeline does, since each throw is differenced against the previous frame
rather than against an empty board.

Subfolders are walked recursively, and series are keyed by their path relative
to the input root — so identically named throws in different capture setups
(e.g. `setup1/throw1`, `setup2/throw1`) stay separate. The annotated `_results`
folder mirrors that same subfolder structure.

**Ground truth (optional).** Drop a `ground_truth.txt` into any folder to score
accuracy, not just "a dart was found somewhere". One line per dart frame,
`<frame stem> <segment>`, where the segment is the called-out label exactly as
the detector reports it — `S5`, `T20`, `D16`, `BULL`, `25`, `MISS`:

    # setup1/ground_truth.txt
    throw1_dart1 S5
    throw1_dart2 T20
    throw1_dart3 D16

Blank lines and `#` comments are ignored. When any truth file is present, the run
prints a segment-accuracy summary and writes `_results/accuracy.md` listing every
mismatch. `--truth-template` bootstraps these files from the current detections so
you only correct the wrong ones instead of typing every dart by hand.

    uv run python scripts/detection/test_detection.py
    uv run python scripts/detection/test_detection.py path/to/images --out results
    uv run python scripts/detection/test_detection.py --truth-template

For every pair it prints the located segment and writes an annotated copy with
the dart's axis and tip drawn on, so the fit can be judged by eye. The reference
frame of each series is calibrated once; the rest are registered onto it.
"""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.entity.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.entity.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402

from scripts.common import (  # noqa: E402
    clear_results,
    collect_images,
    load_image,
    mirrored_dir,
)

OVERLAY_SUFFIX = "_detected.jpg"
GROUND_TRUTH_NAME = "ground_truth.txt"
TRUTH_TEMPLATE_NAME = "ground_truth.template.txt"
REPORT_NAME = "accuracy.md"

FRAME_PATTERN = re.compile(r"^(?P<series>.+?)_(?P<frame>base|dart\d+)$", re.IGNORECASE)

COLOUR_AXIS = (255, 0, 255)  # magenta
COLOUR_TIP = (0, 255, 255)  # yellow
COLOUR_MASK = (60, 200, 60)


@dataclass
class Result:
    """One detection attempt, and how it compares to ground truth (if any)."""

    series: str  # relative series key, e.g. "setup1/throw1"
    frame: str  # frame label within the series, e.g. "dart1"
    path: Path  # the source frame the dart was located in
    located: bool  # whether a dart blob was found at all
    detected: str | None  # segment label if located, else None
    expected: str | None  # ground-truth label if annotated, else None

    @property
    def correct(self) -> bool:
        """Located, annotated, and the detected segment matches the truth."""
        return self.located and self.expected is not None and self.detected == self.expected


def frame_order(name: str) -> tuple[int, int]:
    """Sort key putting `base` first, then dart1, dart2, ... numerically."""
    return (0, 0) if name.lower() == "base" else (1, int(name[4:]))


def collect_series(root: Path, out_dir: Path) -> dict[str, list[tuple[str, Path]]]:
    """Group the photos under `root` (recursively) into throw series.

    Keyed by the path relative to `root` so identically named throws in
    different subfolders stay separate (`setup1/throw1` vs `setup2/throw1`); a
    flat folder keeps its bare series name. Anything under `out_dir` is skipped,
    since that is where this script writes its own annotated copies.
    """
    series: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for path in collect_images(root, out_dir):
        match = FRAME_PATTERN.match(path.stem)
        if match:
            key = (path.parent.relative_to(root) / match["series"]).as_posix()
            series[key].append((match["frame"], path))

    for frames in series.values():
        frames.sort(key=lambda item: frame_order(item[0]))
    return dict(sorted(series.items()))


def load_ground_truth(folder: Path) -> dict[str, str]:
    """Read `<folder>/ground_truth.txt` into {frame stem: expected label}.

    Format is one `<frame stem> <label>` per line (e.g. `throw1_dart1 S5`); blank
    lines and `#` comments are ignored. Labels are upper-cased so `t20` and `T20`
    both work. Returns {} if the file is absent.
    """
    path = folder / GROUND_TRUTH_NAME
    if not path.is_file():
        return {}
    truth: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            print(f"  ! {path.parent.name}/{GROUND_TRUTH_NAME}: skipping malformed line {line!r}")
            continue
        stem, label = parts
        truth[stem] = label.upper()
    return truth


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


def run_series(
    name: str, frames: list[tuple[str, Path]], root: Path, out_dir: Path, raw: bool
) -> list[Result]:
    """Detect every consecutive pair in one series. Returns one Result per dart.

    Annotated copies land under `out_dir` in the same subfolder the source frame
    sat in relative to `root`, so the results tree mirrors the input tree. If the
    series' folder has a `ground_truth.txt`, each Result carries the expected
    label and the console line ends in `gt=<label> OK|MISMATCH`.
    """
    if len(frames) < 2:
        print(f"{name}: only {len(frames)} frame(s), nothing to compare")
        return []

    truth = load_ground_truth(frames[0][1].parent)

    reference = load_image(frames[0][1], raw)
    if reference is None:
        print(f"{name}: reference {frames[0][1].name} unreadable")
        return []

    calibration = board_detector.detect_board(reference)
    if isinstance(calibration, CalibrationFailure):
        print(f"{name}: reference calibration failed ({calibration.value})")
        # Still report the darts as attempted-but-unlocated, so a series whose
        # reference will not calibrate counts against accuracy rather than
        # silently vanishing from the denominator.
        return [
            Result(name, label, path, located=False, detected=None, expected=truth.get(path.stem))
            for label, path in frames[1:]
        ]

    print(f"{name}  reference {frames[0][1].name}  ({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)")

    results: list[Result] = []
    for (_, _previous), (label, path) in zip(frames, frames[1:]):
        expected = truth.get(path.stem)
        frame = load_image(path, raw)
        if frame is None:
            print(f"  {label:<6} UNREADABLE")
            results.append(Result(name, label, path, False, None, expected))
            continue

        outcome = dart_detector.detect_dart(reference, frame, calibration)
        if isinstance(outcome, DetectionFailure):
            detected, located = None, False
            line = f"  {label:<6} FAIL  {outcome.value}  (inliers {dart_detector.trace.alignment_inliers})"
        else:
            detected, located = outcome.segment.label, True
            x, y = outcome.tip_board
            line = (
                f"  {label:<6} {outcome.segment.label:<5} = {outcome.points:<3} "
                f"tip=({x:6.1f},{y:6.1f})mm  r={np.hypot(x, y):5.1f}  "
                f"inliers {dart_detector.trace.alignment_inliers}"
            )
            target_dir = mirrored_dir(path, root, out_dir)
            cv2.imwrite(str(target_dir / f"{path.stem}{OVERLAY_SUFFIX}"), annotate(outcome))

        result = Result(name, label, path, located, detected, expected)
        if expected is not None:
            line += f"   gt={expected} {'OK' if result.correct else 'MISMATCH'}"
        print(line)
        results.append(result)

        # Each dart is differenced against the frame before it, so the aligned
        # copy of this frame becomes the reference for the next one. Aligned,
        # not raw, or the reference drifts out of the calibration's frame.
        if dart_detector.trace.aligned is not None:
            reference = dart_detector.trace.aligned

    return results


def write_report(results: list[Result], out_dir: Path) -> Path:
    """Write a Markdown accuracy report and return its path."""
    labelled = [r for r in results if r.expected is not None]
    correct = [r for r in labelled if r.correct]
    mismatches = [r for r in labelled if not r.correct]

    lines = [
        "# Detection accuracy",
        "",
        "Segment-level comparison against `ground_truth.txt`. *Located* means a dart",
        "blob was found; *correct* means its segment matched the expected label.",
        "",
        f"- Pairs attempted: **{len(results)}**",
        f"- Located: **{sum(r.located for r in results)}/{len(results)}**",
        f"- Correct segment: **{len(correct)}/{len(labelled)}** "
        f"({100 * len(correct) / len(labelled):.1f}%)",
        "",
        "## Per setup",
        "",
        "| setup | correct | total | accuracy |",
        "|---|---|---|---|",
    ]

    by_setup: dict[str, list[Result]] = defaultdict(list)
    for r in labelled:
        by_setup[r.series.split("/")[0] if "/" in r.series else "."].append(r)
    for setup in sorted(by_setup):
        group = by_setup[setup]
        hits = sum(r.correct for r in group)
        lines.append(f"| {setup} | {hits} | {len(group)} | {100 * hits / len(group):.0f}% |")

    lines += ["", f"## Mismatches ({len(mismatches)})", ""]
    if mismatches:
        lines += ["| series | frame | expected | detected |", "|---|---|---|---|"]
        lines += [
            f"| {r.series} | {r.frame} | {r.expected} | {r.detected or 'FAIL'} |"
            for r in mismatches
        ]
    else:
        lines.append("None — every labelled dart matched.")
    lines.append("")

    report = out_dir / REPORT_NAME
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def write_truth_templates(results: list[Result]) -> list[Path]:
    """Write a `ground_truth.template.txt` per folder, seeded with detections.

    A convenience so the user corrects the wrong labels instead of typing every
    dart. Named `.template.txt` on purpose: it is not read back as truth until
    renamed to `ground_truth.txt`.
    """
    by_folder: dict[Path, list[Result]] = defaultdict(list)
    for r in results:
        by_folder[r.path.parent].append(r)

    written = []
    for folder, group in sorted(by_folder.items()):
        group.sort(key=lambda r: r.path.stem)
        lines = [
            f"# Ground truth for {folder.name}. Correct each label against the video,",
            f"# then rename this file to {GROUND_TRUTH_NAME}.",
            "# Format: <frame stem> <segment>   e.g. S5 / T20 / D16 / BULL / 25 / MISS",
            "# Labels below are the CURRENT DETECTIONS — a guess to fix, not truth.",
            "",
        ]
        lines += [f"{r.path.stem} {r.detected or 'MISS'}" for r in group]
        target = folder / TRUTH_TEMPLATE_NAME
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    default_images = _BACKEND / "testdata" / "detection"

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "images", nargs="?", default=default_images, type=Path, help="folder of throw series"
    )
    parser.add_argument("--out", type=Path, default=None, help="where to write annotated copies")
    parser.add_argument("--series", default=None, help="only run series whose name contains this")
    parser.add_argument(
        "--truth-template",
        action="store_true",
        help=f"write a {TRUTH_TEMPLATE_NAME} per folder, pre-filled with the current "
        f"detections, to bootstrap ground truth (correct, then rename to {GROUND_TRUTH_NAME})",
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
        return 1

    out_dir = args.out or args.images / "_results"

    series = collect_series(args.images, out_dir)
    if args.series:
        series = {k: v for k, v in series.items() if args.series in k}
    if not series:
        print(f"no throw series in {args.images} (expected <name>_base.JPG, <name>_dart1.JPG, ...)")
        return 1

    clear_results(out_dir, args.images)

    all_results: list[Result] = []
    for name, frames in series.items():
        all_results.extend(run_series(name, frames, args.images, out_dir, args.raw))
        print()

    located = sum(r.located for r in all_results)
    print(f"{located}/{len(all_results)} darts located")

    labelled = [r for r in all_results if r.expected is not None]
    if labelled:
        correct = sum(r.correct for r in labelled)
        print(f"{correct}/{len(labelled)} correct segment ({100 * correct / len(labelled):.1f}%)")
        print(f"accuracy report: {write_report(all_results, out_dir)}")
    else:
        print(
            f"(no {GROUND_TRUTH_NAME} found in any folder - add one to score accuracy, "
            "or pass --truth-template to bootstrap)"
        )

    if args.truth_template:
        written = write_truth_templates(all_results)
        print(f"wrote {len(written)} {TRUTH_TEMPLATE_NAME} file(s)")

    if located:
        print(f"annotated copies in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
