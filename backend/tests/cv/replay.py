"""Replays the regression dataset through calibration and detection the way the
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
from scripts.common import collect_images, load_image
from scripts.detection.run_all import NO_CHANGE_LABEL, collect_series, load_ground_truth

# Board points (mm) whose image position pins down a calibration: the bull and the
# outer edge of the double ring at 20, 6, 3 and 11.
_BOARD_POINTS = np.array([[0, 0], [0, 170], [170, 0], [0, -170], [-170, 0]], dtype=float)
_EMPTY_READINGS = {DetectionFailure.NO_CHANGE.value, DetectionFailure.DARTS_REMOVED.value}
_FAILURES = {failure.value for failure in DetectionFailure}

# One manifest entry: a dataset folder, and the series it contributes (None for all).
Entry = tuple[str, set[str] | None]


def dataset_root() -> Path | None:
    """Where the regression dataset lives on this machine, if it has one."""
    root = os.environ.get("TESTDATA_DIR")
    return Path(root) / "regression" if root else None


def manifest(name: str) -> list[Entry]:
    """The entries of `tests/cv/<name>.txt`."""
    entries = []
    for line in Path(__file__).with_name(f"{name}.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            folder, *series = line.split()
            entries.append((folder, set(series) or None))
    return entries


def is_correct(result: str, expected: str | None) -> bool:
    """Whether a detection awarded what the throw was worth."""
    if expected is None:
        return False
    if result in _FAILURES:
        return result in _EMPTY_READINGS and expected == NO_CHANGE_LABEL
    return result == expected


def _calibration(image: np.ndarray) -> dict[str, Any]:
    outcome = board_detector.detect_board(image)
    if isinstance(outcome, CalibrationFailure):
        return {"failure": outcome.value, "points": None}
    return {"failure": None, "points": _image_points(outcome)}


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


def series_of(root: Path, entry: Entry) -> dict[str, list[tuple[str, Path]]]:
    """The throw series an entry contributes, keyed by their path in the dataset."""
    folder, wanted = root / entry[0], entry[1]
    assert folder.is_dir(), f"{entry[0]} is missing in {root}"
    return {
        f"{entry[0]}/{name}": frames
        for name, frames in collect_series(folder, folder / "_results").items()
        if wanted is None or name in wanted
    }


def replay(root: Path, entries: list[Entry]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Calibrations (photos and series bases) and detections, each detection with
    the label the players accepted where it is known."""
    calibrations, detections = {}, {}
    for entry in entries:
        folder = root / entry[0]
        if entry[0].startswith("calibration/"):
            for path in collect_images(folder, folder / "_results"):
                calibrations[path.relative_to(root).as_posix()] = _calibration(load_image(path, raw=False))
            continue
        truth = load_ground_truth(folder)
        for key, frames in series_of(root, entry).items():
            calibrations[key], results = replay_series(frames)
            name = key.rsplit("/", 1)[1]
            for label, result in results.items():
                expected = truth.get(f"{name}_{label}", (None, False))[0]
                detections[f"{key}_{label}"] = {"result": result, "expected": expected}
    return calibrations, detections
