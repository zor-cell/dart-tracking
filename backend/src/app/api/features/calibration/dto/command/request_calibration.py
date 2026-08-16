from typing import Literal

from app.api.core.dto.base import CamelModel


class RequestCalibrationDto(CamelModel):
    """Client -> server: have the game's cameras calibrate again.

    Carries nothing. A device without a picture of its own — the scoreboard —
    cannot calibrate, only ask; which cameras are asked is the room's business,
    and each answers from its own frame.
    """

    type: Literal["request_calibration"]
