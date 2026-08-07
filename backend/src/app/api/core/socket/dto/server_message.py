"""Everything the server sends, discriminated by `type`.

Named after the sender, like `ClientMessage`. It carries no discriminator —
nothing on this side parses these. What it types is what may leave through the
hub, so a schema outside the protocol cannot be pushed to a device.
"""

from app.api.core.socket.dto.connection_established import ConnectionEstablishedDto
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.detection.dto.detection_result import DetectionResultDto
from app.api.features.game.dto.game_state import GameStateDto

ServerMessage = (
    ConnectionEstablishedDto | CalibrationResultDto | DetectionResultDto | GameStateDto
)
