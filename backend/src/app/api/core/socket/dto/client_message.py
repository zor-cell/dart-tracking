"""Everything a client sends, discriminated by `type`.

Named after the sender, so the term means the same here as in the frontend's
`client-message.ts`. The union is the only place that knows the full set; each
message is defined by the feature that handles it.

`Field(discriminator="type")` lets pydantic pick the member by that field, so
the socket parses once at the boundary and dispatches on the concrete type. An
unknown tag fails here and never reaches a handler.
"""

from typing import Annotated

from pydantic import Field, TypeAdapter

from app.api.core.socket.dto.command.set_role import SetRoleDto
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.calibration.dto.command.request_calibration import (
    RequestCalibrationDto,
)
from app.api.features.detection.dto.detection_frame import DetectionFrameDto
from app.api.features.game.dto.command.game_command import GameCommand

ClientMessage = Annotated[
    CalibrationFrameDto
    | RequestCalibrationDto
    | DetectionFrameDto
    | SetRoleDto
    | GameCommand,
    Field(discriminator="type"),
]

# Built once: a TypeAdapter compiles its validator on construction.
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
