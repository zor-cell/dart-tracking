"""In-memory store of the devices the server knows.

Process-local, lost on restart. See docs/feature/multi-device.md §5.
"""

from uuid import uuid4

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole


class ClientStore:
    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}

    def resolve(self, client_id: str | None) -> Client:
        """The device behind a connection: found, or created on the spot. An
        unknown id is kept rather than replaced, and the role is left as it was
        — changing it takes a `set_role` command."""
        client = self._clients.get(client_id) if client_id else None

        if client is None:
            client = Client(id=client_id or uuid4().hex, role=DeviceRole.SCOREBOARD)
            self._clients[client.id] = client

        return client


store = ClientStore()
