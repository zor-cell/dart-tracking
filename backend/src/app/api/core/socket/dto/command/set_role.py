from typing import Literal

from app.api.core.domain.device_role import DeviceRole
from app.api.core.dto.base import CamelModel


class SetRoleDto(CamelModel):
    """Client -> server: what this device does in the game from now on.

    A command rather than a handshake parameter. The role lives on the client
    record and outlives the socket, so a connect only has to identify the
    device; the one moment the role actually changes — the way into a game — is
    then stated explicitly instead of riding along on every connect.
    """

    type: Literal["set_role"]
    role: DeviceRole
