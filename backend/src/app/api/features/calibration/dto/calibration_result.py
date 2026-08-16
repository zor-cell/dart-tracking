from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services.board_overlay import build_overlay


class CalibrationResultDto(CamelModel):
    """Server -> client: outcome of a calibration attempt.

    `overlay` holds the recognised board drawn back onto the camera picture, as
    polylines in normalized (0..1) image coordinates, so the client can show
    what was detected and the user can judge whether it is right.

    The homography itself stays on the server. It maps pixels of *the reference
    frame* to board millimetres, and the client's live picture is not that frame
    — every incoming frame is registered onto the reference before the mapping
    is applied. Applied client-side it would be wrong by however far the camera
    has drifted since, so the already-projected overlay is what crosses the
    wire.

    `failure` names which stage gave up, so the client can advise what to
    change rather than only reporting that it did not work.
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
