from typing import Literal

from app.api.core.dto.base import CamelModel


class RequestCalibrationDto(CamelModel):
    """Client -> server: have the game's cameras calibrate again."""

    type: Literal["request_calibration"]
