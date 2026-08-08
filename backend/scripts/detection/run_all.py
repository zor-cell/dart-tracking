"""Run dart detection over folders of throw series and report what happened.

Expects `<series>_base.JPG`, `<series>_dart1.JPG`, ... - every consecutive pair is
one detection (`base -> dart1`, `dart1 -> dart2`, ...), as live, where each throw
is differenced against the previous frame and not against an empty board.
Subfolders are walked recursively and series keyed by their relative path, so
`setup1/throw1` and `setup2/throw1` stay separate; `_results` mirrors that
structure and holds an annotated copy (axis + tip) per dart.

Usage:
    uv run python scripts/detection/run_all.py
    uv run python scripts/detection/run_all.py path/to/images --out results
    uv run python scripts/detection/run_all.py --only-mismatches
    uv run python scripts/detection/run_all.py --truth-template

`--only-mismatches` keeps the run and the report exactly as they are but writes
an image only where the detection disagrees with ground truth, so `_results`
becomes a folder of just the failures instead of 165 mostly-correct overlays.

Ground truth (optional): a `ground_truth.txt` in a folder scores segment accuracy
and writes `_results/accuracy.md` with every mismatch. One `<frame stem> <segment>`
per line, labels exactly as the detector reports them; blank lines and `#` comments
are ignored. A trailing `?` marks a label you were unsure of - still scored as
given, only flagged. `--truth-template` bootstraps these files from the current
detections.

    throw1_dart1 S5
    throw1_dart2 T20
    throw1_dart3 D16?
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

from app.api.features.calibration.domain.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.detection.domain.detection_failure import DetectionFailure  # noqa: E402
from app.api.features.detection.services import dart_detector  # noqa: E402

from scripts.common import (  # noqa: E402
    clear_results,
    collect_images,
    load_image,
    location_of,
    mirrored_dir,
    rate_table,
    setup_of,
    write_markdown,
)

OVERLAY_SUFFIX = "_detected.jpg"
FAILURE_SUFFIX = "_failed.jpg"
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
    uncertain: bool = False  # truth label was flagged `?` (I wasn't sure); still scored as-is

    @property
    def correct(self) -> bool:
        """Located, annotated, and the detected segment matches the truth."""
        return self.located and self.expected is not None and self.detected == self.expected


def frame_order(name: str) -> tuple[int, int]:
    """Sort key putting `base` first, then dart1, dart2, ... numerically."""
    return (0, 0) if name.lower() == "base" else (1, int(name[4:]))


def collect_series(root: Path, out_dir: Path) -> dict[str, list[tuple[str, Path]]]:
    """Group the photos under `root` (recursively) into throw series.

    Keyed by the path relative to `root`, so identically named throws in
    different subfolders stay separate. `out_dir` is skipped.
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


def load_ground_truth(folder: Path) -> dict[str, tuple[str, bool]]:
    """Read `<folder>/ground_truth.txt` into {frame stem: (expected label, uncertain)}.

    Labels are upper-cased so `t20` and `T20` both work; a trailing `?` is
    stripped and returned as the uncertainty flag. Returns {} if the file is absent.
    """
    path = folder / GROUND_TRUTH_NAME
    if not path.is_file():
        return {}
    truth: dict[str, tuple[str, bool]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            print(f"  ! {path.parent.name}/{GROUND_TRUTH_NAME}: skipping malformed line {line!r}")
            continue
        stem, label = parts
        label = label.upper()
        uncertain = label.endswith("?")
        truth[stem] = (label.rstrip("?"), uncertain)
    return truth


def expected_for(truth: dict[str, tuple[str, bool]], stem: str) -> tuple[str | None, bool]:
    """Look up a frame stem, yielding (label or None, uncertain)."""
    return truth.get(stem, (None, False))


def annotate(dart) -> np.ndarray:
    """Draw the located dart onto the aligned frame it was found in.

    Not the reference: the dart is only visible in the newer frame, and drawing on
    the older one would show a marker floating over bare board.
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


def annotate_failure(failure: DetectionFailure) -> np.ndarray | None:
    """Draw what a dart that was never located left behind, if anything.

    A failure has no axis and no tip to mark, so the useful content is the change
    mask and the name of the stage that gave up. Without this, the darts that
    went most wrong would be the only ones with no picture at all.
    """
    canvas = dart_detector.trace.aligned
    if canvas is None:
        canvas = dart_detector.trace.frame
    if canvas is None:
        return None

    canvas = canvas.copy()
    if dart_detector.trace.change_mask is not None:
        canvas[dart_detector.trace.change_mask > 0] = COLOUR_MASK
    cv2.putText(
        canvas,
        f"FAILED: {failure.value}",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        COLOUR_TIP,
        2,
        cv2.LINE_AA,
    )
    return canvas


def run_series(
    name: str,
    frames: list[tuple[str, Path]],
    root: Path,
    out_dir: Path,
    raw: bool,
    only_mismatches: bool = False,
) -> list[Result]:
    """Detect every consecutive pair in one series. Returns one Result per dart.

    Annotated copies land under `out_dir`, mirroring the input tree. With a
    `ground_truth.txt` present, each console line ends in `gt=<label> OK|MISMATCH`;
    `only_mismatches` then narrows the copies to just those, so the output folder
    holds exactly the darts worth looking at.
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
        unlocated = []
        for label, path in frames[1:]:
            expected, uncertain = expected_for(truth, path.stem)
            unlocated.append(Result(name, label, path, False, None, expected, uncertain))
        return unlocated

    print(f"{name}  reference {frames[0][1].name}  ({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)")

    results: list[Result] = []
    for (_, _previous), (label, path) in zip(frames, frames[1:]):
        expected, uncertain = expected_for(truth, path.stem)
        frame = load_image(path, raw)
        if frame is None:
            print(f"  {label:<6} UNREADABLE")
            results.append(Result(name, label, path, False, None, expected, uncertain))
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

        result = Result(name, label, path, located, detected, expected, uncertain)
        if expected is not None:
            mark = "?" if uncertain else ""
            line += f"   gt={expected}{mark} {'OK' if result.correct else 'MISMATCH'}"
        print(line)
        results.append(result)

        # An unlabelled dart cannot be called a mismatch, so --only-mismatches
        # drops it rather than guessing: the point of the flag is a folder where
        # everything in it is known to be wrong.
        if only_mismatches and (expected is None or result.correct):
            pass
        else:
            image = annotate(outcome) if located else annotate_failure(outcome)
            if image is not None:
                suffix = OVERLAY_SUFFIX if located else FAILURE_SUFFIX
                target_dir = mirrored_dir(path, root, out_dir)
                cv2.imwrite(str(target_dir / f"{path.stem}{suffix}"), image)

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
    uncertain = sum(r.uncertain for r in labelled)

    lines = [
        "# Detection accuracy",
        "",
        "Segment-level comparison against `ground_truth.txt`. *Located* means a dart",
        "blob was found; *correct* means its segment matched the expected label.",
        "A `?` suffix in the truth file marks a label I wasn't sure about; it is still",
        "scored against as-is and just flagged here.",
        "",
        f"- Pairs attempted: **{len(results)}**",
        f"- Located: **{sum(r.located for r in results)}/{len(results)}**",
        f"- Correct segment: **{len(correct)}/{len(labelled)}** "
        f"({100 * len(correct) / len(labelled):.1f}%)",
        f"- Uncertain truth labels (`?`): **{uncertain}/{len(labelled)}**",
        "",
    ]

    # Location is the physical board (`pz` across its setups), setup the
    # individual capture folder (`pz_setup1`); both derived from the series key.
    lines += ["## Per location (board)", ""]
    lines += rate_table(labelled, lambda r: location_of(r.series), lambda r: r.correct, "location", "correct")
    lines += ["", "## Per setup", ""]
    lines += rate_table(labelled, lambda r: setup_of(r.series), lambda r: r.correct, "setup", "correct")

    lines += ["", f"## Mismatches ({len(mismatches)})", ""]
    if mismatches:
        lines += ["| series | frame | expected | detected |", "|---|---|---|---|"]
        lines += [
            f"| {r.series} | {r.frame} | {r.expected}{'?' if r.uncertain else ''} | {r.detected or 'FAIL'} |"
            for r in mismatches
        ]
    else:
        lines.append("None — every labelled dart matched.")
    lines.append("")

    return write_markdown(out_dir, REPORT_NAME, lines)


def write_truth_templates(results: list[Result]) -> list[Path]:
    """Write a `ground_truth.template.txt` per folder, seeded with detections.

    Named `.template.txt` on purpose: not read back as truth until renamed.
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
        "--only-mismatches",
        action="store_true",
        help="write annotated copies only for darts that disagree with "
        f"{GROUND_TRUTH_NAME} (unlabelled darts are skipped). Every series is still "
        "run and the accuracy report is unchanged - this only narrows the images "
        "on disk to the ones worth looking at",
    )
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
        "client's downscale and JPEG compression (for comparison only - the "
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
        all_results.extend(
            run_series(name, frames, args.images, out_dir, args.raw, args.only_mismatches)
        )
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

    if args.only_mismatches:
        wrong = sum(1 for r in labelled if not r.correct)
        print(f"{wrong} mismatch image(s) in {out_dir}" if wrong else "no mismatches to write")
    elif located:
        print(f"annotated copies in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
