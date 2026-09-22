"""Everything the server sends, discriminated by `type`.

Named after the sender, like `ClientMessage`. It carries no discriminator —
nothing on this side parses these. What it types is what may leave through the
hub, so a schema outside the protocol cannot be pushed to a device.
"""

from app.api.core.socket.dto.client_state import ClientStateDto
from app.api.features.announcement.dto.announcer_state import AnnouncerStateDto
from app.api.features.announcement.dto.dart_announcement import DartAnnouncementDto
from app.api.features.calibration.dto.calibration_requested import (
    CalibrationRequestedDto,
)
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.calibration.dto.calibration_state import CalibrationStateDto
from app.api.features.calibration.dto.calibration_status import CalibrationStatusDto
from app.api.features.detection.dto.detection_result import DetectionResultDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.rematch_started import RematchStartedDto

ServerMessage = (
    ClientStateDto
    | CalibrationRequestedDto
    | CalibrationResultDto
    | CalibrationStateDto
    | CalibrationStatusDto
    | DetectionResultDto
    | GameStateDto
    | AnnouncerStateDto
    | DartAnnouncementDto
    | RematchStartedDto
)
