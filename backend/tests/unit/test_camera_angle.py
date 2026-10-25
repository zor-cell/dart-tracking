import math

import numpy as np
import pytest

from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.camera_angle import camera_angle

WIDTH, HEIGHT = 1280, 720


def calibration_seen_from(camera: tuple[float, float, float], focal: float) -> Calibration:
    """The calibration a pinhole camera at `camera` (board mm), aimed at the bullseye, would yield."""
    centre = np.array(camera, dtype=float)
    forward = -centre / np.linalg.norm(centre)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rotation = np.vstack([right, down, forward])
    translation = -rotation @ centre
    intrinsics = np.array([[focal, 0, WIDTH / 2], [0, focal, HEIGHT / 2], [0, 0, 1]])
    board_to_image = intrinsics @ np.column_stack([rotation[:, 0], rotation[:, 1], translation])
    return Calibration(
        homography=np.linalg.inv(board_to_image), image_width=WIDTH, image_height=HEIGHT
    )


@pytest.mark.parametrize("focal", [900.0, 1500.0])
@pytest.mark.parametrize("camera", [(-800.0, -400.0, 1500.0), (600.0, 300.0, 1200.0)])
def test_viewing_angles_are_recovered(camera, focal):
    x, y, z = camera

    angle = camera_angle(calibration_seen_from(camera, focal))

    assert angle is not None
    assert angle.horizontal == pytest.approx(math.degrees(math.atan2(x, z)), abs=0.5)
    assert angle.vertical == pytest.approx(math.degrees(math.atan2(y, z)), abs=0.5)
    assert angle.tilt == pytest.approx(math.degrees(math.acos(z / math.hypot(x, y, z))), abs=0.5)
