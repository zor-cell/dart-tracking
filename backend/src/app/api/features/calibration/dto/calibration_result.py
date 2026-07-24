from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure
from app.api.features.calibration.services.board_overlay import build_overlay


class CalibrationResult(CamelModel):
    """Server -> client: outcome of a calibration attempt.

    `overlay` holds the recognised board drawn back onto the camera picture, as
    polylines in normalized (0..1) image coordinates, so the client can show
    what was detected and the user can judge whether it is right.

    `failure` names which stage gave up, so the client can advise what to
    change rather than only reporting that it did not work.
    """

    type: Literal["calibration_result"] = "calibration_result"
    success: bool
    homography: list[list[float]] | None = None
    overlay: list[list[list[float]]] | None = None
    failure: CalibrationFailure | None = None

    @classmethod
    def from_calibration(cls, calibration: Calibration) -> Self:
        return cls(
            success=True,
            homography=calibration.to_list(),
            overlay=build_overlay(calibration),
        )

    @classmethod
    def failed(cls, failure: CalibrationFailure) -> Self:
        return cls(success=False, failure=failure)
