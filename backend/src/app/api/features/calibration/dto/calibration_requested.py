from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationRequestedDto(CamelModel):
    """Server -> camera: take a fresh frame and calibrate from it."""

    type: Literal["calibration_requested"] = "calibration_requested"
