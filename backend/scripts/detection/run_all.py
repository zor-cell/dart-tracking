"""Run dart detection over folders of throw series and report what happened.

Expects `<series>_base.JPG`, `<series>_dart1.JPG`, ... - every consecutive pair is
one detection (`base -> dart1`, `dart1 -> dart2`, ...), as live, where each throw
is differenced against the previous frame and not against an empty board.
Subfolders are walked recursively and series keyed by their relative path, so
`setup1/throw1` and `setup2/throw1` stay separate; `_results` mirrors that
structure and holds an annotated copy per dart: the change mask, the fitted axis
and tip, and — in cyan — the board model the calibration's homography implies.
The model is what makes the picture readable: a tip a segment away from the truth
is a calibration bug if the cyan rings sit beside the real rings, and a detection
bug if they sit on them. Each copy is captioned with how far the camera moved
between the two frames, which is the other thing that cannot be seen by looking.

Usage:
    uv run python scripts/detection/run_all.py
    uv run python scripts/detection/run_all.py path/to/images --out results
    uv run python scripts/detection/run_all.py --only-mismatches
    uv run python scripts/detection/run_all.py --truth-template

`--only-mismatches` keeps the run and the report exactly as they are but writes
an image only where the detection disagrees with ground truth, so `_results`
becomes a folder of just the failures instead of 165 mostly-correct overlays.

A `NO_CHANGE` failure is correct only against the label `NO_CHANGE`, which means
the frame shows no new dart at all — it bounced out or never stuck. `MISS` is a
dart sitting in the surround, which the pipeline is expected to find.

Ground truth (optional): a `ground_truth.txt` in a folder scores segment accuracy
and writes `_results/accuracy.md` with every mismatch, each with how far in
millimetres the scored tip landed from the segment it should have been in — a
couple of millimetres is a wire's-width miss, tens of millimetres is a different
kind of error. One `<frame stem> <segment>`
per line, labels exactly as the detector reports them; blank lines and `#` comments
are ignored. A trailing `?` marks a label you were unsure of - still scored as
given, only flagged. `--truth-template` bootstraps these files from the current
detections.

    throw1_dart1 S5
    throw1_dart2 T20
    throw1_dart3 D16?
    throw1_dart4 NO_CHANGE
"""

import argparse
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Import app.* from src/ (as `--app-dir src` does at runtime) and scripts.* from
# the backend root, regardless of where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.domain.board_geometry import (  # noqa: E402
    distance_to_segment,
    segment_from_label,
)
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure  # noqa: E402
from app.api.features.calibration.domain.calibration import Calibration  # noqa: E402
from app.api.features.calibration.services import board_detector  # noqa: E402
from app.api.features.calibration.services.board_overlay import build_overlay  # noqa: E402
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
# Truth label for a frame that shows no new dart at all — distinct from `MISS`,
# which is a dart sitting in the surround.
NO_CHANGE_LABEL = "NO_CHANGE"
TRUTH_TEMPLATE_NAME = "ground_truth.template.txt"
REPORT_NAME = "accuracy.md"

FRAME_PATTERN = re.compile(r"^(?P<series>.+?)_(?P<frame>base|dart\d+)$", re.IGNORECASE)

# A mismatch closer than this to the expected segment counts as a near miss: the
# wire between two segments is about 1 mm wide, and tip precision is a few mm.
NEAR_MISS_MM = 5.0

COLOUR_AXIS = (255, 0, 255)  # magenta
COLOUR_TIP = (0, 255, 255)  # yellow
COLOUR_MASK = (60, 200, 60)
COLOUR_MODEL = (255, 255, 0)  # cyan — the board model the homography implies

# Camera movement between two frames, in pixels, past which the registration's
# sub-pixel remainder starts producing apparent change of its own.
SHAKE_WARN_PX = 8.0


@dataclass
class Result:
    """One detection attempt, and how it compares to ground truth (if any)."""

    series: str  # relative series key, e.g. "setup1/throw1"
    frame: str  # frame label within the series, e.g. "dart1"
    path: Path  # the source frame the dart was located in
    located: bool  # whether a dart blob was found at all
    detected: str | None  # segment label if located, else None
    expected: str | None  # ground-truth label if annotated, else None
    tip_board: tuple[float, float] | None = None  # scored tip in board mm, if located
    uncertain: bool = False  # truth label was flagged `?` (I wasn't sure); still scored as-is
    shift_px: float = 0.0  # how far the camera moved between reference and frame
    failure: DetectionFailure | None = None  # which stage gave up, if none was located
    fragments: int = 0  # components the scored blob was fused from
    largest_share: float = 0.0  # share of the blob's pixels in its largest component
    anchor_to_tip_mm: float = 0.0  # distance from the anchoring fragment to the tip

    @property
    def read_empty(self) -> bool:
        """Whether finding nothing was the right answer here.

        Only against the label `NO_CHANGE`, which says the frame holds no new
        dart. A `MISS` is a dart in the surround and has to be found: scoring it
        the same would credit a failed detection for landing on zero points.
        `ALIGNMENT_FAILED` never qualifies — that is the pipeline unable to look,
        not a reading of the board.
        """
        return (
            self.failure in (DetectionFailure.NO_CHANGE, DetectionFailure.DARTS_REMOVED)
            and self.expected == NO_CHANGE_LABEL
        )

    @property
    def correct(self) -> bool:
        """The pipeline awarded what the throw was actually worth."""
        if self.expected is None:
            return False
        if self.located:
            return self.detected == self.expected
        return self.read_empty

    @property
    def off_by_mm(self) -> float | None:
        """How far the scored tip landed from the expected segment, in millimetres.

        Zero on a correct call. What it buys on a mismatch is the difference
        between a tip a wire's width off the right segment — plausible, the
        pipeline was essentially right — and one tens of millimetres away, which
        means something upstream (calibration, alignment, the wrong blob) is
        wrong rather than imprecise. None when there is nothing to measure: no
        tip, no truth label, or a label that does not parse.
        """
        if self.tip_board is None or self.expected is None:
            return None
        segment = segment_from_label(self.expected)
        if segment is None:
            return None
        return distance_to_segment(*self.tip_board, segment)


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


def draw_board_model(canvas: np.ndarray, calibration: Calibration) -> None:
    """Draw the board the homography implies: ring circles and sector wires.

    The scored millimetres are only ever as good as this mapping, so a tip that
    sits a segment away is two different bugs depending on whether these lines
    sit on the real wires or beside them. Without the model in the picture, a
    calibration error and a detection error look exactly alike.

    Drawn on the aligned frame, which shares the reference's pixel grid — the
    grid the calibration belongs to.
    """
    height, width = canvas.shape[:2]
    for polyline in build_overlay(calibration):
        points = np.array([[x * width, y * height] for x, y in polyline])
        cv2.polylines(canvas, [points.astype(np.int32)], False, COLOUR_MODEL, 1, cv2.LINE_AA)


def annotate(dart, calibration: Calibration) -> np.ndarray:
    """Draw the located dart onto the aligned frame it was found in.

    Not the reference: the dart is only visible in the newer frame, and drawing on
    the older one would show a marker floating over bare board.
    """
    canvas = dart_detector.trace.aligned.copy()
    if dart_detector.trace.change_mask is not None:
        canvas[dart_detector.trace.change_mask > 0] = COLOUR_MASK
    draw_board_model(canvas, calibration)

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
    return caption(canvas, model_caption())


def model_caption() -> list[str]:
    """The two numbers needed to read the board model drawn over the frame."""
    trace = dart_detector.trace
    shake = f"camera moved {trace.alignment_shift_px:.1f} px"
    if trace.alignment_shift_px > SHAKE_WARN_PX:
        shake += "  (!)"
    return [f"cyan: board model at {trace.pixels_per_mm:.2f} px/mm", shake]


def caption(canvas: np.ndarray, lines: list[str]) -> np.ndarray:
    """Stamp lines into the top-left corner, dark stroke under light text."""
    for index, line in enumerate(lines):
        origin = (8, 20 + index * 18)
        cv2.putText(canvas, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(
            canvas, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA
        )
    return canvas


def annotate_failure(failure: DetectionFailure, calibration: Calibration) -> np.ndarray | None:
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
    # Only once the frames were aligned is the model in the right grid; before
    # that it would be drawn against a frame it does not belong to.
    if dart_detector.trace.aligned is not None:
        draw_board_model(canvas, calibration)
    return caption(canvas, [f"FAILED: {failure.value}"] + model_caption())


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
            unlocated.append(Result(name, label, path, False, None, expected, uncertain=uncertain))
        return unlocated

    print(f"{name}  reference {frames[0][1].name}  ({dart_detector._pixels_per_mm(calibration.homography):.2f} px/mm)")

    empty_board = reference
    results: list[Result] = []
    for (_, _previous), (label, path) in zip(frames, frames[1:]):
        expected, uncertain = expected_for(truth, path.stem)
        frame = load_image(path, raw)
        if frame is None:
            print(f"  {label:<6} UNREADABLE")
            results.append(Result(name, label, path, False, None, expected, uncertain=uncertain))
            continue

        outcome = dart_detector.detect_dart(reference, frame, calibration, empty_board)
        shift = dart_detector.trace.alignment_shift_px
        shake = "!" if shift > SHAKE_WARN_PX else " "
        failure = outcome if isinstance(outcome, DetectionFailure) else None
        if failure is not None:
            detected, located, tip_board = None, False, None
            line = f"  {label:<6} FAIL  {outcome.value}  (inliers {dart_detector.trace.alignment_inliers})"
        else:
            detected, located, tip_board = outcome.segment.label, True, outcome.tip_board
            x, y = outcome.tip_board
            line = (
                f"  {label:<6} {outcome.segment.label:<5} = {outcome.points:<3} "
                f"tip=({x:6.1f},{y:6.1f})mm  r={np.hypot(x, y):5.1f}  "
                f"inliers {dart_detector.trace.alignment_inliers}"
            )
        line += f"  shift {shift:5.1f}px{shake}"

        result = Result(
            name, label, path, located, detected, expected, tip_board, uncertain, shift, failure,
            dart_detector.trace.fragment_count,
            dart_detector.trace.largest_fragment_share,
            dart_detector.trace.anchor_to_tip_mm,
        )
        if expected is not None:
            mark = "?" if uncertain else ""
            verdict = "OK" if result.correct else "MISMATCH"
            if result.read_empty:
                verdict = "OK (frame holds no new dart)"
            line += f"   gt={expected}{mark} {verdict}"
            if not result.correct and result.off_by_mm is not None:
                line += f" (off {result.off_by_mm:.1f}mm)"
        print(line)
        results.append(result)

        # An unlabelled dart cannot be called a mismatch, so --only-mismatches
        # drops it rather than guessing: the point of the flag is a folder where
        # everything in it is known to be wrong.
        if only_mismatches and (expected is None or result.correct):
            pass
        else:
            image = (
                annotate(outcome, calibration)
                if located
                else annotate_failure(outcome, calibration)
            )
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


SHAKE_BUCKETS = ((2.0, "< 2 px (still)"), (5.0, "2 - 5 px"), (10.0, "5 - 10 px"), (1e9, "> 10 px"))


def shake_table(labelled: list[Result]) -> list[str]:
    """Accuracy against how far the camera moved between the two frames.

    Registration is supposed to make this irrelevant, so a rate that falls off
    with movement says the sub-pixel remainder is costing segments — which is a
    different fix from a better fit, and worth being able to see rather than
    argue about.
    """
    rows = ["| camera movement | correct | total | rate | mean off by |", "|---|---|---|---|---|"]
    for limit, label in SHAKE_BUCKETS:
        lower = max((l for l, _ in SHAKE_BUCKETS if l < limit), default=0.0)
        bucket = [r for r in labelled if lower <= r.shift_px < limit]
        if not bucket:
            continue
        correct = sum(r.correct for r in bucket)
        offsets = [r.off_by_mm for r in bucket if r.off_by_mm is not None]
        mean_off = f"{sum(offsets) / len(offsets):.1f} mm" if offsets else "—"
        rows.append(
            f"| {label} | {correct} | {len(bucket)} | "
            f"{100 * correct / len(bucket):.0f}% | {mean_off} |"
        )
    return rows


FRAGMENT_BUCKETS = ((1, "1 (one blob)"), (2, "2"), (4, "3 - 4"), (10**9, "5+"))


def median(values: Iterable[float]) -> float:
    """Middle value, or 0.0 if there is nothing to take a middle of."""
    ordered = list(values)
    return statistics.median(ordered) if ordered else 0.0


def cohesion_table(labelled: list[Result]) -> list[str]:
    """Accuracy against how many components the scored dart was fused from.

    The goal in docs/feature/erkennung-blob.md §1 is one component per dart, and
    the segment rate alone cannot say whether a change moved towards it. This
    can: it counts the fusing itself, and shows what each extra piece costs.
    """
    located = [r for r in labelled if r.located]
    if not located:
        return []

    whole = [r for r in located if r.fragments == 1]
    right = [r for r in located if r.correct]
    wrong = [r for r in located if not r.correct]
    rows = [
        f"- Arrived as one component: **{len(whole)}/{len(located)}** "
        f"({100 * len(whole) / len(located):.0f}%)",
        f"- Median share of the blob in its largest component: "
        f"**{100 * median(r.largest_share for r in located):.0f}%**",
        f"- Median anchor-to-tip distance: **{median(r.anchor_to_tip_mm for r in right):.0f} mm** "
        f"on correct calls, **{median(r.anchor_to_tip_mm for r in wrong):.0f} mm** on mismatches",
        "",
        "| fragments | correct | total | rate | mean off by |",
        "|---|---|---|---|---|",
    ]
    for limit, label in FRAGMENT_BUCKETS:
        lower = max((l for l, _ in FRAGMENT_BUCKETS if l < limit), default=0)
        bucket = [r for r in located if lower < r.fragments <= limit]
        if not bucket:
            continue
        correct = sum(r.correct for r in bucket)
        offsets = [r.off_by_mm for r in bucket if r.off_by_mm is not None]
        mean_off = f"{sum(offsets) / len(offsets):.1f} mm" if offsets else "—"
        rows.append(
            f"| {label} | {correct} | {len(bucket)} | "
            f"{100 * correct / len(bucket):.0f}% | {mean_off} |"
        )
    return rows


def write_report(results: list[Result], out_dir: Path) -> Path:
    """Write a Markdown accuracy report and return its path."""
    labelled = [r for r in results if r.expected is not None]
    correct = [r for r in labelled if r.correct]
    mismatches = [r for r in labelled if not r.correct]
    uncertain = sum(r.uncertain for r in labelled)

    read_empty = [r for r in labelled if r.read_empty]
    lines = [
        "# Detection accuracy",
        "",
        "Segment-level comparison against `ground_truth.txt`. *Located* means a dart",
        "blob was found; *correct* means the pipeline awarded what the throw was worth.",
        "A `?` suffix in the truth file marks a label I wasn't sure about; it is still",
        "scored against as-is and just flagged here.",
        "",
        "`NO_CHANGE` counts as **correct** only against the label `NO_CHANGE`: a frame",
        "with no new dart in it. A `MISS` is a dart in the surround and has to be found —",
        "crediting `NO_CHANGE` there would score the points, not the detection.",
        "`ALIGNMENT_FAILED` never counts: that is the pipeline failing to look.",
        "",
        f"- Pairs attempted: **{len(results)}**",
        f"- Located: **{sum(r.located for r in results)}/{len(results)}**",
        f"- Correct: **{len(correct)}/{len(labelled)}** "
        f"({100 * len(correct) / len(labelled):.1f}%)",
        f"- of those, frames correctly read as `NO_CHANGE`: **{len(read_empty)}**",
        f"- Uncertain truth labels (`?`): **{uncertain}/{len(labelled)}**",
        "",
    ]

    # Location is the physical board (`pz` across its setups), setup the
    # individual capture folder (`pz_setup1`); both derived from the series key.
    lines += ["## Per location (board)", ""]
    lines += rate_table(labelled, lambda r: location_of(r.series), lambda r: r.correct, "location", "correct")
    lines += ["", "## Per setup", ""]
    lines += rate_table(labelled, lambda r: setup_of(r.series), lambda r: r.correct, "setup", "correct")

    lines += ["", "## Per camera movement", ""]
    lines += shake_table(labelled)

    lines += [
        "",
        "## Per blob cohesion",
        "",
        "How many components the scored dart had to be fused from. One is the goal:",
        "the dart reached the fit as a single object instead of as pieces the fusion",
        "had to guess back together. The anchor-to-tip distance says the same thing from",
        "the other end: an anchor far from the tip it produced was not part of that dart.",
        "",
    ]
    lines += cohesion_table(labelled)

    lines += ["", f"## Mismatches ({len(mismatches)})", ""]
    if mismatches:
        near = sum(1 for r in mismatches if r.off_by_mm is not None and r.off_by_mm <= NEAR_MISS_MM)
        lines += [
            "*off by* is the distance from the scored tip to the nearest point of the",
            "expected segment. A few millimetres means the pipeline was essentially right",
            "and landed on the wrong side of a wire; tens of millimetres means it was wrong",
            "about something bigger. Sorted nearest first, unmeasurable (no tip) last.",
            "",
            f"- Within {NEAR_MISS_MM:.0f} mm of the expected segment: "
            f"**{near}/{len(mismatches)}**",
            "",
            "| series | frame | expected | detected | off by | fragments | anchor to tip "
            "| camera moved |",
            "|---|---|---|---|---|---|---|---|",
        ]
        # None sorts last: a dart that was never located has no distance, and it
        # is a different kind of failure from one that landed in the wrong place.
        mismatches.sort(key=lambda r: (r.off_by_mm is None, r.off_by_mm or 0.0))
        lines += [
            f"| {r.series} | {r.frame} | {r.expected}{'?' if r.uncertain else ''} "
            f"| {r.detected or (r.failure.value if r.failure else 'FAIL')} "
            f"| {f'{r.off_by_mm:.1f} mm' if r.off_by_mm is not None else '—'} "
            f"| {r.fragments or '—'} "
            f"| {f'{r.anchor_to_tip_mm:.0f} mm' if r.located else '—'} "
            f"| {r.shift_px:.1f} px{' !' if r.shift_px > SHAKE_WARN_PX else ''} |"
            for r in mismatches
        ]
    else:
        lines.append("None — every labelled dart matched.")
    lines.append("")

    return write_markdown(out_dir, REPORT_NAME, lines)


def template_label(result: Result) -> str:
    """The seed label for a frame: what the detector said, as a truth label."""
    if result.detected is not None:
        return result.detected
    empty = (DetectionFailure.NO_CHANGE, DetectionFailure.DARTS_REMOVED)
    return NO_CHANGE_LABEL if result.failure in empty else "MISS"


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
            "# Format: <frame stem> <segment>   e.g. S5 / T20 / D16 / BULL / 25 / MISS,",
            "# or NO_CHANGE when the frame shows no new dart at all.",
            "# Labels below are the CURRENT DETECTIONS — a guess to fix, not truth.",
            "",
        ]
        lines += [f"{r.path.stem} {template_label(r)}" for r in group]
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
        read_empty = sum(r.read_empty for r in labelled)
        print(f"{correct}/{len(labelled)} correct ({100 * correct / len(labelled):.1f}%)")
        if read_empty:
            print(f"  ({read_empty} of them frames correctly read as NO_CHANGE)")
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
