from typing import Literal, Self

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.dto.base import CamelModel


class ConnectionEstablishedDto(CamelModel):
    """Server -> client: sent once right after the WebSocket handshake.

    It tells the device who it is. The `clientId` is the device's name from here
    on — minted on the first ever connect, sent back on every later one — and
    the role is what the server has on record for it, which is how a device that
    just reloaded finds out what it was.
    """

    type: Literal["connection_established"] = "connection_established"
    client_id: str
    role: DeviceRole

    @classmethod
    def from_entity(cls, client: Client) -> Self:
        return cls(client_id=client.id, role=client.role)
