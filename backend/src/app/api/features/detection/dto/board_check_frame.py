from typing import Literal

from app.api.core.dto.base import CamelModel


class BoardCheckFrameDto(CamelModel):
    """Client -> server: a still frame of the empty board to check the calibration against."""

    type: Literal["board_check_frame"]
    image: str  # base64-encoded JPEG
