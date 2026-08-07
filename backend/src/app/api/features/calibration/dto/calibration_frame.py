from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationFrameDto(CamelModel):
    """Client -> server: a single still frame to calibrate the board against."""

    type: Literal["calibration_frame"]
    image: str  # base64-encoded JPEG
    # Off unless the client asks: on, the server dumps per-stage debug images.
    debug: bool = False
