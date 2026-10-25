"""Calibration and detection over the regression corpus, or its gate subset, against
one committed baseline. Accept intended changes with `--update-baseline`."""

import json
import math
import warnings
from pathlib import Path
from typing import Any

import pytest

from tests.cv.replay import corpus_root, is_correct, manifest, replay

pytestmark = [
    pytest.mark.skipif(corpus_root() is None, reason="TESTDATA_DIR is not set"),
    pytest.mark.timeout(3 * 60 * 60),
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
def cv_set(request) -> str:
    return request.config.getoption("--cv-set")


@pytest.fixture(scope="module")
def replayed(cv_set) -> tuple[dict[str, Any], dict[str, Any]]:
    return replay(corpus_root(), manifest(cv_set))


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def update(path: Path, results: dict[str, Any], cv_set: str) -> None:
    """The gate only refreshes its own entries; the corpus replaces the whole baseline."""
    merged = results if cv_set == "corpus" else read(path) | results
    path.write_text(json.dumps(merged, indent=1, sort_keys=True) + "\n")


def unknown(path: Path, baseline: dict[str, Any], results: dict[str, Any], cv_set: str) -> list[str]:
    """Keys the baseline should hold but does not, or holds but the replay did not produce."""
    missing = [f"{key}: new" for key in sorted(results.keys() - baseline.keys())]
    if cv_set == "corpus":
        missing += [f"{key}: gone" for key in sorted(baseline.keys() - results.keys())]
    assert baseline, f"no baseline yet: run the corpus with --update-baseline to create {path.name}"
    return missing


def report(path: Path, lines: list[str]) -> str:
    return f"{len(lines)} result(s) differ from {path.name}; accept with --update-baseline:\n  " + "\n  ".join(lines)


def test_calibration(replayed, cv_set, request):
    results = replayed[0]
    if request.config.getoption("--update-baseline"):
        update(CALIBRATION_BASELINE, results, cv_set)
        return
    baseline = read(CALIBRATION_BASELINE)

    changed = unknown(CALIBRATION_BASELINE, baseline, results, cv_set)
    for key in sorted(results.keys() & baseline.keys()):
        before, after = baseline[key], results[key]
        if before["failure"] != after["failure"]:
            changed.append(f"{key}: {before['failure'] or 'calibrated'} -> {after['failure'] or 'calibrated'}")
        elif before["points"] is not None:
            moved = max(math.dist(a, b) for a, b in zip(before["points"], after["points"], strict=True))
            if moved > TOLERANCE_PX:
                changed.append(f"{key}: board moved {moved:.1f} px")

    assert not changed, report(CALIBRATION_BASELINE, changed)


def test_detection(replayed, cv_set, request):
    results = replayed[1]
    baseline = read(DETECTION_BASELINE)
    if request.config.getoption("--update-baseline"):
        # Where no ground truth sits next to the frames, the labels already in the baseline stay.
        for key, entry in results.items():
            entry["expected"] = entry["expected"] or baseline.get(key, {}).get("expected")
        update(DETECTION_BASELINE, results, cv_set)
        return

    missing = unknown(DETECTION_BASELINE, baseline, results, cv_set)
    assert not missing, report(DETECTION_BASELINE, missing)

    changed, regressed = [], 0
    for key in sorted(results):
        before, after, truth = baseline[key]["result"], results[key]["result"], baseline[key]["expected"]
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
