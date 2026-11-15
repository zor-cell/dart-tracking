from typing import Literal, Self

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.dto.base import CamelModel


class ClientStateDto(CamelModel):
    """Server -> client: what the server holds about this device, with its `clientId`.

    Sent right after the handshake and after every `set_role`.
    """

    type: Literal["client_state"] = "client_state"
    client_id: str
    role: DeviceRole

    @classmethod
    def from_entity(cls, client: Client) -> Self:
        return cls(client_id=client.id, role=client.role)
