from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationResultMessage(CamelModel):
    """Server -> client: outcome of a calibration attempt.

    `homography` is a stub for now (identity matrix on success) — real board
    detection (Hough/contour -> homography) lands once test footage from
    zeitplan.md Phase 1 is available.
    """

    type: Literal["calibration_result"] = "calibration_result"
    success: bool
    homography: list[list[float]] | None = None
