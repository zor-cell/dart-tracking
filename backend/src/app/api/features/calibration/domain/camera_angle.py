"""Where the camera stood, as viewing angles onto the board, read off a calibration."""

import math
from dataclasses import dataclass

import numpy as np

from app.api.features.calibration.domain.calibration import Calibration

# Fallback focal length when the homography cannot pin it down: a typical phone
# main camera, as a 35 mm equivalent over the image diagonal.
_FALLBACK_FOCAL_35MM = 26.0
_FULL_FRAME_DIAGONAL_MM = math.hypot(36.0, 24.0)
# Plausible focal lengths as multiples of the long image edge.
_FOCAL_RANGE = (0.5, 3.0)


@dataclass(frozen=True)
class CameraAngle:
    """Viewing angles in degrees. `horizontal` < 0: left of the board seen from
    the oche; `vertical` < 0: below the bullseye; `tilt`: off the board normal."""

    tilt: float
    horizontal: float
    vertical: float
    focal_px: float


def camera_angle(calibration: Calibration) -> CameraAngle | None:
    """The viewing angles of the camera this calibration was taken with."""
    board_to_image, focal = _centred_projection(calibration)
    centre = _camera_centre(board_to_image, focal)
    if centre is None:
        return None
    x, y, z = centre
    return CameraAngle(
        tilt=math.degrees(math.acos(z / math.sqrt(x * x + y * y + z * z))),
        horizontal=math.degrees(math.atan2(x, z)),
        vertical=math.degrees(math.atan2(y, z)),
        focal_px=focal,
    )


def outward_direction(calibration: Calibration, x: float, y: float) -> np.ndarray | None:
    """Image displacement (px) of a point 1 mm off the board at (x, y), towards the camera."""
    board_to_image, focal = _centred_projection(calibration)
    scaled = np.diag([1.0 / focal, 1.0 / focal, 1.0]) @ board_to_image
    norm = (np.linalg.norm(scaled[:, 0]) + np.linalg.norm(scaled[:, 1])) / 2
    if norm == 0.0:
        return None
    sign = 1.0 if scaled[2, 2] > 0 else -1.0
    normal = np.cross(scaled[:, 0], scaled[:, 1])
    lift = np.diag([focal, focal, 1.0]) @ (normal / np.linalg.norm(normal)) * norm * sign

    on_board = board_to_image @ np.array([x, y, 1.0])
    raised = on_board + lift
    if on_board[2] == 0.0 or raised[2] == 0.0:
        return None
    return raised[:2] / raised[2] - on_board[:2] / on_board[2]


def _centred_projection(calibration: Calibration) -> tuple[np.ndarray, float]:
    """Board -> image with the image centre as origin, and the focal length in pixels."""
    width, height = calibration.image_width, calibration.image_height
    to_centre = np.array([[1.0, 0.0, -width / 2], [0.0, 1.0, -height / 2], [0.0, 0.0, 1.0]])
    board_to_image = to_centre @ calibration.inverse

    focal = _estimate_focal(board_to_image, max(width, height))
    if focal is None:
        focal = _FALLBACK_FOCAL_35MM * math.hypot(width, height) / _FULL_FRAME_DIAGONAL_MM
    return board_to_image, focal


def _estimate_focal(board_to_image: np.ndarray, long_edge: int) -> float | None:
    """Focal length in pixels from the two rotation columns being orthogonal and
    of equal length, or None where the view is too frontal to tell."""
    h1, h2 = board_to_image[:, 0], board_to_image[:, 1]
    planar = np.array(
        [h1[0] * h2[0] + h1[1] * h2[1], h1[0] ** 2 + h1[1] ** 2 - h2[0] ** 2 - h2[1] ** 2]
    )
    depth = np.array([h1[2] * h2[2], h1[2] ** 2 - h2[2] ** 2])
    denominator = float(depth @ depth)
    if denominator == 0.0:
        return None

    squared = -float(planar @ depth) / denominator
    if squared <= 0.0:
        return None
    focal = math.sqrt(squared)
    low, high = _FOCAL_RANGE
    return focal if low * long_edge <= focal <= high * long_edge else None


def _camera_centre(board_to_image: np.ndarray, focal: float) -> np.ndarray | None:
    """Camera position in board millimetres (x right, y up, z out of the board)."""
    scaled = np.diag([1.0 / focal, 1.0 / focal, 1.0]) @ board_to_image
    norm = (np.linalg.norm(scaled[:, 0]) + np.linalg.norm(scaled[:, 1])) / 2
    if norm == 0.0:
        return None
    # The board lies in front of the camera, so its depth is positive.
    scale = (1.0 if scaled[2, 2] > 0 else -1.0) / norm
    r1, r2, translation = scale * scaled[:, 0], scale * scaled[:, 1], scale * scaled[:, 2]

    u, _, vt = np.linalg.svd(np.column_stack([r1, r2, np.cross(r1, r2)]))
    rotation = u @ vt
    centre = -rotation.T @ translation
    return centre if centre[2] > 0 else None
