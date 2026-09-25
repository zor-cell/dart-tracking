from typing import Literal

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration_state import CalibrationState


class CalibrationStateDto(CamelModel):
    """Server -> room: how far the game's board calibration is."""

    type: Literal["calibration_state"] = "calibration_state"
    state: CalibrationState
