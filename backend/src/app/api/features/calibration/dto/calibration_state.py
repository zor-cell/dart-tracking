from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationStateDto(CamelModel):
    """Server -> room: whether the game has a calibrated camera that scores it."""

    type: Literal["calibration_state"] = "calibration_state"
    calibrated: bool
