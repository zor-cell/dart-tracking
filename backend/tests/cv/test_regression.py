"""Calibration and detection over the recorded games in `games.txt`, against a
committed baseline. Accept intended changes with `--update-baseline`."""

import json
import math
import warnings
from pathlib import Path
from typing import Any

import pytest

from tests.cv.replay import is_correct, recordings, replay_games

pytestmark = [
    pytest.mark.skipif(recordings() is None, reason="TESTDATA_DIR is not set"),
    pytest.mark.timeout(1800),
]

HERE = Path(__file__).parent
CALIBRATION_BASELINE = HERE / "baseline_calibration.json"
DETECTION_BASELINE = HERE / "baseline_detection.json"
# How far a projected board point may move before the calibration counts as changed.
TOLERANCE_PX = 2.0
# Share of darts that may score worse than the baseline before the test fails: OpenCV
# builds for different platforms disagree on a few borderline frames.
REGRESSION_BUDGET = 0.03


@pytest.fixture(scope="module")
def replayed() -> tuple[dict[str, Any], dict[str, Any]]:
    return replay_games(recordings())


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def write(path: Path, results: dict[str, Any]) -> None:
    path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")


def report(path: Path, lines: list[str]) -> str:
    return f"{len(lines)} result(s) differ from {path.name}; accept with --update-baseline:\n  " + "\n  ".join(lines)


def test_calibration(replayed, request):
    results = replayed[0]
    if request.config.getoption("--update-baseline"):
        write(CALIBRATION_BASELINE, results)
        return
    expected = read(CALIBRATION_BASELINE)
    assert expected, f"no baseline yet: run with --update-baseline to create {CALIBRATION_BASELINE.name}"

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

    assert not changed, report(CALIBRATION_BASELINE, changed)


def test_detection(replayed, request):
    results = replayed[1]
    expected = read(DETECTION_BASELINE)
    if request.config.getoption("--update-baseline"):
        # Where no ground truth sits next to the frames, the labels already in the baseline stay.
        for key, entry in results.items():
            entry["expected"] = entry["expected"] or expected.get(key, {}).get("expected")
        write(DETECTION_BASELINE, results)
        return
    assert expected, f"no baseline yet: run with --update-baseline to create {DETECTION_BASELINE.name}"
    assert expected.keys() == results.keys(), report(DETECTION_BASELINE, sorted(expected.keys() ^ results.keys()))

    changed, regressed = [], 0
    for key in sorted(results):
        before, after, truth = expected[key]["result"], results[key]["result"], expected[key]["expected"]
        if before == after:
            continue
        verdict = {(False, True): "improved", (True, False): "regressed"}.get(
            (is_correct(before, truth), is_correct(after, truth)), "changed"
        )
        regressed += verdict == "regressed"
        changed.append(f"{key}: {before} -> {after} (truth {truth}, {verdict})")

    budget = max(2, int(REGRESSION_BUDGET * len(results)))
    assert regressed <= budget, report(DETECTION_BASELINE, changed)
    if changed:
        warnings.warn(report(DETECTION_BASELINE, changed), stacklevel=1)
