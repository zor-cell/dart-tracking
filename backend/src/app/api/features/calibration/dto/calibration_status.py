from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto


class CalibrationStatusDto(CamelModel):
    """Server -> requester: whether a camera's calibration attempt worked.

    The slim counterpart to `CalibrationResultDto`, which only its own camera
    can use — its overlay is in that camera's pixel grid. Without this, a
    scoreboard that asked for a recalibration would never learn it failed.
    """

    type: Literal["calibration_status"] = "calibration_status"
    success: bool

    @classmethod
    def from_result(cls, result: CalibrationResultDto) -> Self:
        return cls(success=result.success)
