from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationRequestedDto(CamelModel):
    """Server -> camera: take a fresh frame and calibrate from it.

    Only the trigger travels to the cameras. The result cannot come back the
    same way: an overlay is drawn in the pixel grid of the camera that produced
    it, so each camera answers its own `calibration_result` and the room learns
    the outcome through `calibration_state`.
    """

    type: Literal["calibration_requested"] = "calibration_requested"
