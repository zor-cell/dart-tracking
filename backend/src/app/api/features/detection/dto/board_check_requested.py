from typing import Literal

from app.api.core.dto.base import CamelModel


class BoardCheckRequestedDto(CamelModel):
    """Server -> camera: send a fresh frame to confirm the calibration still fits."""

    type: Literal["board_check_requested"] = "board_check_requested"
