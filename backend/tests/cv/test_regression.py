"""Calibration and detection against a committed baseline. Every difference is
reported; accept intended ones with `--update-baseline`."""

import json
import math
import os
import warnings
from pathlib import Path
from typing import Any

import pytest

from tests.cv.replay import calibrations, detections

HERE = Path(__file__).parent
SUBSET = HERE.parent / "data"
# How far a projected board point may move before the calibration counts as changed.
TOLERANCE_PX = 2.0
# Share of darts that may score worse than the baseline before the test fails: OpenCV
# builds for different platforms disagree on a few borderline frames.
REGRESSION_BUDGET = 0.03

_full = os.environ.get("TESTDATA_DIR")
DATASETS = [
    pytest.param(SUBSET, "baseline", id="subset"),
    pytest.param(
        Path(_full) if _full else None,
        "baseline_full",
        id="full",
        marks=[
            pytest.mark.cv_full,
            pytest.mark.timeout(1800),
            pytest.mark.skipif(not _full, reason="TESTDATA_DIR is not set"),
        ],
    ),
]


def load_or_update(results: dict[str, Any], path: Path, update: bool) -> dict[str, Any] | None:
    if update:
        path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
        return None
    assert path.exists(), f"no baseline yet: run with --update-baseline to create {path.name}"
    return json.loads(path.read_text())


def report(path: Path, lines: list[str]) -> str:
    return f"{len(lines)} result(s) differ from {path.name}; accept with --update-baseline:\n  " + "\n  ".join(lines)


@pytest.mark.parametrize(("root", "baseline"), DATASETS)
def test_calibration(root, baseline, request):
    path = HERE / f"{baseline}_calibration.json"
    results = calibrations(root / "calibration")
    expected = load_or_update(results, path, request.config.getoption("--update-baseline"))
    if expected is None:
        return

    changed = []
    for key in sorted(expected.keys() | results.keys()):
        before, after = expected.get(key), results.get(key)
        if before is None or after is None:
            changed.append(f"{key}: {'new' if before is None else 'gone'}")
        elif before["failure"] != after["failure"]:
            changed.append(f"{key}: {before['failure'] or 'calibrated'} -> {after['failure'] or 'calibrated'}")
        elif before["points"] is not None:
            moved = max(math.dist(a, b) for a, b in zip(before["points"], after["points"], strict=True))
            if moved > TOLERANCE_PX:
                changed.append(f"{key}: board moved {moved:.1f} px")

    assert not changed, report(path, changed)


@pytest.mark.parametrize(("root", "baseline"), DATASETS)
def test_detection(root, baseline, request):
    path = HERE / f"{baseline}_detection.json"
    results = detections(root / "detection")
    expected = load_or_update(results, path, request.config.getoption("--update-baseline"))
    if expected is None:
        return

    assert expected.keys() == results.keys(), report(path, sorted(expected.keys() ^ results.keys()))
    changed, regressed = [], 0
    for key in sorted(results):
        before, after = expected[key], results[key]
        if (before["result"], before["expected"]) == (after["result"], after["expected"]):
            continue
        verdict = {(False, True): "improved", (True, False): "regressed"}.get(
            (before["correct"], after["correct"]), "changed"
        )
        regressed += verdict == "regressed"
        changed.append(f"{key}: {before['result']} -> {after['result']} (truth {after['expected']}, {verdict})")

    budget = max(2, int(REGRESSION_BUDGET * len(results)))
    assert regressed <= budget, report(path, changed)
    if changed:
        warnings.warn(report(path, changed), stacklevel=1)
