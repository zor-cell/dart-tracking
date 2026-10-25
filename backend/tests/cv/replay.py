"""Runs calibration and detection over a test tree the way the live socket does,
and reduces each result to what a regression baseline compares."""

from pathlib import Path
from typing import Any

import numpy as np

from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from scripts.common import collect_images, load_image
from scripts.detection.run_all import Result, collect_series, load_ground_truth

# Board points (mm) whose image position pins down a calibration: the bull and the
# outer edge of the double ring at 20, 6, 3 and 11.
_BOARD_POINTS = np.array([[0, 0], [0, 170], [170, 0], [0, -170], [-170, 0]], dtype=float)


def _image_points(calibration: Calibration) -> list[list[float]]:
    projected = np.c_[_BOARD_POINTS, np.ones(len(_BOARD_POINTS))] @ calibration.inverse.T
    return np.round(projected[:, :2] / projected[:, 2:], 1).tolist()


def calibrations(root: Path) -> dict[str, dict[str, Any]]:
    results = {}
    for path in collect_images(root, root / "_results"):
        outcome = board_detector.detect_board(load_image(path, raw=False))
        failed = isinstance(outcome, CalibrationFailure)
        results[path.relative_to(root).as_posix()] = {
            "failure": outcome.value if failed else None,
            "points": None if failed else _image_points(outcome),
        }
    return results


def detections(root: Path) -> dict[str, dict[str, Any]]:
    results = {}
    for name, frames in collect_series(root, root / "_results").items():
        truth = load_ground_truth(frames[0][1].parent)
        empty_board = reference = load_image(frames[0][1], raw=False)
        calibration = board_detector.detect_board(reference)

        for label, path in frames[1:]:
            expected = truth.get(path.stem, (None, False))[0]
            key = f"{name}_{label}"
            if isinstance(calibration, CalibrationFailure):
                results[key] = {"result": f"calibration {calibration.value}", "expected": expected, "correct": False}
                continue

            outcome = dart_detector.detect_dart(reference, load_image(path, raw=False), calibration, empty_board)
            aligned = dart_detector.trace.aligned
            failed = isinstance(outcome, DetectionFailure)
            result = Result(
                name, label, path, not failed, None if failed else outcome.segment.label, expected,
                failure=outcome if failed else None,
            )
            results[key] = {
                "result": outcome.value if failed else outcome.segment.label,
                "expected": expected,
                "correct": result.correct,
            }
            # The socket keeps a failed frame as the next reference only when the change was absorbed.
            absorbed = dart_detector.trace.rejected_miss or outcome is DetectionFailure.DARTS_REMOVED
            if aligned is not None and (not failed or absorbed):
                reference = aligned
    return results
