import cv2
import numpy as np
import pytest

from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.detection.domain.board_check import (
    MAX_SHIFT_MM,
    MIN_COVERAGE,
    MIN_INLIERS,
    BoardCheck,
)
from app.api.features.detection.services.dart_detector import check_board
from app.api.features.detection.services.detection_store import DetectionStore

ALIGNED = np.zeros((4, 4, 3), np.uint8)

# 1.125 mm per pixel around the image centre: the scoring area spans 400 px.
SCALE = 225 / 200
CALIBRATION = Calibration(
    np.array([[SCALE, 0, -320 * SCALE], [0, SCALE, -240 * SCALE], [0, 0, 1.0]]), 640, 480
)


def board() -> np.ndarray:
    rng = np.random.default_rng(7)
    image = np.full((480, 640, 3), 128, np.uint8)
    for _ in range(600):
        centre = (int(rng.integers(0, 640)), int(rng.integers(0, 480)))
        colour = tuple(int(v) for v in rng.integers(0, 256, 3))
        cv2.circle(image, centre, int(rng.integers(3, 18)), colour, -1)
    return image


def shifted(image: np.ndarray, pixels: int) -> np.ndarray:
    move = np.float32([[1, 0, pixels], [0, 1, 0]])
    return cv2.warpAffine(image, move, image.shape[1::-1], borderMode=cv2.BORDER_REFLECT)


def check(**fields) -> BoardCheck:
    return BoardCheck(
        **({"inliers": MIN_INLIERS, "shift_mm": MAX_SHIFT_MM, "coverage": MIN_COVERAGE, "aligned": ALIGNED} | fields)
    )


def test_a_check_at_every_limit_holds():
    assert check().holds


@pytest.mark.parametrize(
    "fields",
    [
        {"inliers": MIN_INLIERS - 1},
        {"shift_mm": MAX_SHIFT_MM + 0.1},
        {"coverage": MIN_COVERAGE - 0.01},
        {"shift_mm": None},
        {"aligned": None},
    ],
)
def test_a_check_past_any_limit_does_not_hold(fields):
    assert not check(**fields).holds


def test_a_board_nudged_a_few_millimetres_still_holds():
    anchor = board()

    result = check_board(shifted(anchor, 4), anchor, CALIBRATION)

    assert result.holds
    assert result.shift_mm == pytest.approx(4 * SCALE, abs=0.5)
    assert result.aligned is not None and result.aligned.shape == anchor.shape


def test_a_board_moved_by_centimetres_does_not_hold():
    anchor = board()

    result = check_board(shifted(anchor, 30), anchor, CALIBRATION)

    assert result.shift_mm == pytest.approx(30 * SCALE, abs=1)
    assert not result.holds


def test_a_frame_without_the_board_does_not_align():
    anchor = board()

    result = check_board(np.full_like(anchor, 90), anchor, CALIBRATION)

    assert (result.shift_mm, result.aligned, result.holds) == (None, None, False)


def test_a_refresh_starts_the_visit_over_but_keeps_the_calibration_frame():
    store = DetectionStore()
    calibrated, fresh = board(), np.zeros((480, 640, 3), np.uint8)
    store.seed("game", "camera", calibrated)
    store.add_dart("game", "camera", np.zeros((1, 2), np.float32))

    store.refresh("game", "camera", fresh)

    assert store.get("game", "camera") is fresh
    assert store.empty_board("game", "camera") is fresh
    assert store.anchor("game", "camera") is calibrated
    assert store.darts("game", "camera") == []


def test_a_refresh_with_darts_still_in_keeps_the_empty_board():
    store = DetectionStore()
    calibrated, fresh = board(), np.zeros((480, 640, 3), np.uint8)
    store.seed("game", "camera", calibrated)

    store.refresh("game", "camera", fresh, empty=False)

    assert store.get("game", "camera") is fresh
    assert store.empty_board("game", "camera") is calibrated


def test_the_darts_of_the_ended_visit_are_kept_until_the_next_starts_over():
    store = DetectionStore()
    dart, later = np.zeros((1, 2), np.float32), np.ones((1, 2), np.float32)
    store.seed("game", "camera", board())
    store.add_dart("game", "camera", dart)

    store.end_visit("game")
    assert (store.darts("game", "camera"), store.ended_darts("game", "camera")) == ([], [dart])

    store.end_visit("game")
    assert store.ended_darts("game", "camera") == []

    store.add_dart("game", "camera", later)
    store.end_visit("game")
    store.refresh("game", "camera", board())
    assert store.ended_darts("game", "camera") == []
