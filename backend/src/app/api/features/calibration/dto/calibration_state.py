from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationStateDto(CamelModel):
    """Server -> room: whether the game has a calibrated scoring camera, and
    whether that camera's latest attempt failed."""

    type: Literal["calibration_state"] = "calibration_state"
    calibrated: bool
    failed: bool
