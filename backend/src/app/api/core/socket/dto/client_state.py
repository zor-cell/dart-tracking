from typing import Literal, Self

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.dto.base import CamelModel


class ClientStateDto(CamelModel):
    """Server -> client: what the server holds about this device.

    Sent right after the handshake, where it also carries the `clientId` the
    device is named by from here on, and again after every `set_role`. One
    message for the whole record — the counterpart of `game_state`, which does
    the same for the state the room shares.

    It is what a device that just reloaded reads its role off: the record
    outlives the socket, so the connect only has to say which device this is.
    """

    type: Literal["client_state"] = "client_state"
    client_id: str
    role: DeviceRole

    @classmethod
    def from_entity(cls, client: Client) -> Self:
        return cls(client_id=client.id, role=client.role)
