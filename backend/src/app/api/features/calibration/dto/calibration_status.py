from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto


class CalibrationStatusDto(CamelModel):
    """Server -> room: which camera just calibrated, and whether it worked.

    The slim counterpart to `CalibrationResultDto`, which only its own camera
    can use — its overlay is in that camera's pixel grid. This carries the part
    every device can act on: that a camera is calibrated, or which one is not.
    Without it, a scoreboard that asked for a recalibration would never learn it
    failed.
    """

    type: Literal["calibration_status"] = "calibration_status"
    client_id: str
    success: bool
    failure: CalibrationFailure | None = None

    @classmethod
    def from_result(cls, client_id: str, result: CalibrationResultDto) -> Self:
        return cls(client_id=client_id, success=result.success, failure=result.failure)
