"""Everything the server sends, as a union of the messages the hub may push."""

from app.api.core.socket.dto.client_state import ClientStateDto
from app.api.features.announcement.dto.announcer_state import AnnouncerStateDto
from app.api.features.announcement.dto.calibration_announcement import (
    CalibrationAnnouncementDto,
)
from app.api.features.announcement.dto.dart_announcement import DartAnnouncementDto
from app.api.features.announcement.dto.turn_announcement import TurnAnnouncementDto
from app.api.features.calibration.dto.calibration_requested import (
    CalibrationRequestedDto,
)
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.calibration.dto.calibration_state import CalibrationStateDto
from app.api.features.detection.dto.board_check_requested import BoardCheckRequestedDto
from app.api.features.detection.dto.detection_result import DetectionResultDto
from app.api.features.game.dto.correction_pending import CorrectionPendingDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.rematch_started import RematchStartedDto

ServerMessage = (
    ClientStateDto
    | CalibrationRequestedDto
    | CalibrationResultDto
    | CalibrationStateDto
    | DetectionResultDto
    | BoardCheckRequestedDto
    | GameStateDto
    | AnnouncerStateDto
    | DartAnnouncementDto
    | TurnAnnouncementDto
    | CalibrationAnnouncementDto
    | RematchStartedDto
    | CorrectionPendingDto
)
