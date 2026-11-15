from typing import Literal

from app.api.core.domain.device_role import DeviceRole
from app.api.core.dto.base import CamelModel


class SetRoleDto(CamelModel):
    """Client -> server: what this device does in the game from now on."""

    type: Literal["set_role"]
    role: DeviceRole
