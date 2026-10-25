import cv2
import numpy as np
import pytest

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.socket.services.jpeg_header import jpeg_size
from app.api.features.announcement.domain.announcer import choose_announcer
from app.api.features.calibration.domain.calibration_state import (
    CalibrationState,
    calibration_state,
)
from app.infrastructure import token_bucket
from app.infrastructure.token_bucket import TokenBucket


def encode(extension: str, width: int = 64, height: int = 48) -> bytes:
    ok, buffer = cv2.imencode(extension, np.zeros((height, width, 3), np.uint8))
    assert ok
    return buffer.tobytes()


def test_jpeg_size_reads_the_header():
    assert jpeg_size(encode(".jpg", 640, 480)) == (640, 480)


@pytest.mark.parametrize(
    "data",
    [b"", b"\xff\xd8", encode(".png"), encode(".jpg")[:20], b"\xff\xd8\xff\xe0\x00\x01" + b"\x00" * 20],
)
def test_jpeg_size_rejects_what_is_not_a_complete_jpeg_header(data):
    assert jpeg_size(data) is None


def test_token_bucket_allows_a_burst_then_refills(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(token_bucket.time, "monotonic", lambda: now[0])
    bucket = TokenBucket(rate=2, burst=3)

    assert [bucket.take() for _ in range(4)] == [True, True, True, False]
    now[0] += 0.5
    assert [bucket.take() for _ in range(2)] == [True, False]
    now[0] += 60
    assert sum(bucket.take() for _ in range(5)) == 3


CAMERA = DeviceRole.CAMERA
SCOREBOARD = DeviceRole.SCOREBOARD


@pytest.mark.parametrize(
    ("present", "chosen", "scoring", "announcer"),
    [
        ([("a", CAMERA), ("b", SCOREBOARD)], "a", None, "a"),
        ([("a", CAMERA), ("b", SCOREBOARD)], "gone", None, "b"),
        ([("a", CAMERA), ("b", CAMERA)], None, "b", "b"),
        ([("a", CAMERA), ("b", CAMERA)], None, "gone", "a"),
        ([], "a", "a", None),
    ],
)
def test_announcer_priority(present, chosen, scoring, announcer):
    clients = [Client(id=id, role=role) for id, role in present]
    assert choose_announcer(clients, chosen, scoring) == announcer


@pytest.mark.parametrize(
    ("camera", "scoring", "calibrating", "failed", "state"),
    [
        (False, True, True, True, CalibrationState.NO_CAMERA),
        (True, True, True, True, CalibrationState.CALIBRATING),
        (True, True, False, True, CalibrationState.FAILED),
        (True, True, False, False, CalibrationState.CALIBRATED),
        (True, False, False, False, CalibrationState.UNCALIBRATED),
    ],
)
def test_calibration_state_priority(camera, scoring, calibrating, failed, state):
    assert (
        calibration_state(
            camera_connected=camera,
            scoring_connected=scoring,
            calibrating=calibrating,
            failed=failed,
        )
        is state
    )
