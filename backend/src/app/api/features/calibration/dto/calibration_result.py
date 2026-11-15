from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services.board_overlay import build_overlay


class CalibrationResultDto(CamelModel):
    """Server -> client: outcome of a calibration attempt; `overlay` is the board as
    polylines in normalized image coordinates, `failure` the stage that gave up.
    """

    type: Literal["calibration_result"] = "calibration_result"
    success: bool
    overlay: list[list[list[float]]] | None = None
    failure: CalibrationFailure | None = None

    @classmethod
    def from_calibration(cls, calibration: Calibration) -> Self:
        return cls(success=True, overlay=build_overlay(calibration))

    @classmethod
    def failed(cls, failure: CalibrationFailure) -> Self:
        return cls(success=False, failure=failure)
