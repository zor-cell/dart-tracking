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

from app.api.core.socket.dto.set_role import SetRoleDto
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.detection.dto.detection_frame import DetectionFrameDto
from app.api.features.game.dto.next_player import NextPlayerDto
from app.api.features.game.dto.register_dart import RegisterDartDto
from app.api.features.game.dto.undo import UndoDto

ClientMessage = Annotated[
    CalibrationFrameDto
    | DetectionFrameDto
    | SetRoleDto
    | RegisterDartDto
    | UndoDto
    | NextPlayerDto,
    Field(discriminator="type"),
]

# Built once: a TypeAdapter compiles its validator on construction.
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
