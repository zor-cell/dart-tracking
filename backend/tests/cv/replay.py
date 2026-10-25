"""Replays recorded throw series through calibration and detection the way the
live socket does, reduced to what a regression baseline compares."""

import os
from pathlib import Path
from typing import Any

import numpy as np

from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from scripts.common import load_image
from scripts.detection.run_all import NO_CHANGE_LABEL, collect_series, load_ground_truth

GAMES = [
    line.strip()
    for line in (Path(__file__).with_name("games.txt")).read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
# Board points (mm) whose image position pins down a calibration: the bull and the
# outer edge of the double ring at 20, 6, 3 and 11.
_BOARD_POINTS = np.array([[0, 0], [0, 170], [170, 0], [0, -170], [-170, 0]], dtype=float)
_EMPTY_READINGS = {DetectionFailure.NO_CHANGE.value, DetectionFailure.DARTS_REMOVED.value}
_FAILURES = {failure.value for failure in DetectionFailure}


def recordings() -> Path | None:
    """Where the app keeps recorded games, if this machine has them."""
    root = os.environ.get("TESTDATA_DIR")
    return Path(root) / "evaluation" if root else None


def is_correct(result: str, expected: str | None) -> bool:
    """Whether a detection awarded what the throw was worth."""
    if expected is None:
        return False
    if result in _FAILURES:
        return result in _EMPTY_READINGS and expected == NO_CHANGE_LABEL
    return result == expected


def _image_points(calibration: Calibration) -> list[list[float]]:
    projected = np.c_[_BOARD_POINTS, np.ones(len(_BOARD_POINTS))] @ calibration.inverse.T
    return np.round(projected[:, :2] / projected[:, 2:], 1).tolist()


def replay_series(frames: list[tuple[str, Path]]) -> tuple[dict[str, Any], dict[str, str]]:
    """The calibration of the series' base frame and the result per dart frame, by frame label."""
    empty_board = reference = load_image(frames[0][1], raw=False)
    calibration = board_detector.detect_board(reference)
    if isinstance(calibration, CalibrationFailure):
        failed = {"failure": calibration.value, "points": None}
        return failed, {label: f"calibration {calibration.value}" for label, _ in frames[1:]}

    results = {}
    for label, path in frames[1:]:
        outcome = dart_detector.detect_dart(reference, load_image(path, raw=False), calibration, empty_board)
        failed = isinstance(outcome, DetectionFailure)
        results[label] = outcome.value if failed else outcome.segment.label
        # The socket keeps a failed frame as the next reference only when the change was absorbed.
        absorbed = dart_detector.trace.rejected_miss or outcome is DetectionFailure.DARTS_REMOVED
        if dart_detector.trace.aligned is not None and (not failed or absorbed):
            reference = dart_detector.trace.aligned
    return {"failure": None, "points": _image_points(calibration)}, results


def replay_games(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Calibrations by series and detections by dart over every game in `games.txt`,
    each detection with the label the players accepted, where known."""
    calibrations, detections = {}, {}
    for game in GAMES:
        folder = root / game
        assert folder.is_dir(), f"{game} from games.txt is missing in {root}"
        truth = load_ground_truth(folder)
        for name, frames in collect_series(folder, folder / "_results").items():
            calibration, results = replay_series(frames)
            calibrations[f"{game}/{name}"] = calibration
            for label, result in results.items():
                expected = truth.get(f"{name}_{label}", (None, False))[0]
                detections[f"{game}/{name}_{label}"] = {"result": result, "expected": expected}
    return calibrations, detections
