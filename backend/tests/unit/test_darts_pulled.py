import numpy as np

from app.api.features.detection.services.dart_detector import darts_pulled

EMPTY = np.full((40, 40, 3), 200, np.uint8)
DART = np.array([[x, 20] for x in range(10, 30)], np.float32)
OTHER = np.array([[20, y] for y in range(5, 15)], np.float32)


def with_darts(*blobs: np.ndarray) -> np.ndarray:
    frame = EMPTY.copy()
    for blob in blobs:
        frame[blob[:, 1].astype(int), blob[:, 0].astype(int)] = 30
    return frame


def test_pulled_once_every_located_dart_is_gone():
    assert darts_pulled([DART, OTHER], EMPTY, EMPTY)


def test_not_pulled_while_one_dart_is_still_in():
    assert not darts_pulled([DART, OTHER], with_darts(OTHER), EMPTY)


def test_nothing_located_is_never_pulled():
    assert not darts_pulled([], EMPTY, EMPTY)
