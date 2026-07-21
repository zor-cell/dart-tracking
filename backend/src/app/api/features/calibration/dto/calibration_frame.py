from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationFrameMessage(CamelModel):
    """Client -> server: a single still frame to calibrate the board against."""

    type: Literal["calibration_frame"]
    image: str  # base64-encoded JPEG
    debug: bool = True
