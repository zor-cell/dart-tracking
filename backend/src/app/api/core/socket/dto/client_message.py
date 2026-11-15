"""Everything a client sends, as a union discriminated by `type`; each message is
defined by the feature that handles it.
"""

from typing import Annotated

from pydantic import Field, TypeAdapter

from app.api.core.socket.dto.command.authenticate import AuthenticateDto
from app.api.core.socket.dto.command.set_role import SetRoleDto
from app.api.features.announcement.dto.command.claim_announcer import ClaimAnnouncerDto
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.calibration.dto.command.request_calibration import (
    RequestCalibrationDto,
)
from app.api.features.detection.dto.detection_frame import DetectionFrameDto
from app.api.features.evaluation.dto.command.set_evaluation import SetEvaluationDto
from app.api.features.game.dto.command.game_command import GameCommand
from app.api.features.game.dto.command.set_ended import SetEndedDto
from app.api.features.game.dto.command.set_tracking_paused import SetTrackingPausedDto
from app.api.features.game.dto.command.set_win_confirmed import SetWinConfirmedDto

ClientMessage = Annotated[
    CalibrationFrameDto
    | RequestCalibrationDto
    | DetectionFrameDto
    | SetRoleDto
    | AuthenticateDto
    | SetEvaluationDto
    | ClaimAnnouncerDto
    | SetTrackingPausedDto
    | SetWinConfirmedDto
    | SetEndedDto
    | GameCommand,
    Field(discriminator="type"),
]

# Built once: a TypeAdapter compiles its validator on construction.
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
