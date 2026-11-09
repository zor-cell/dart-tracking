from typing import Literal

from app.api.core.dto.base import CamelModel


class CalibrationAnnouncementDto(CamelModel):
    """Server -> announcer: the board calibration just failed, or holds again
    after a failure. Said once per change, not after every attempt."""

    type: Literal["calibration_announcement"] = "calibration_announcement"
    calibrated: bool
    clips: list[str]
