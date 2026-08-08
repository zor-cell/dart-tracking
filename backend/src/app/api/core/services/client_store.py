"""In-memory store of the devices the server knows.

Process-local like the game store: lost on restart, not shared across workers.
The id is what a device is called from here on — later a row in the database,
which is why it is minted here and not by the client.
"""

from uuid import uuid4

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole


class ClientStore:
    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}

    def resolve(self, client_id: str | None, role: DeviceRole | None) -> Client:
        """The device behind a connection: found, or created on the spot.

        `role` is a claim, sent only when the device has just been told what it
        is (game setup, join screen). Left out on a plain reconnect, so the
        stored role is what answers "what am I" after a reload.

        An id the store does not know is kept rather than replaced. It happens
        whenever the server restarted — which in development is constantly —
        and a device that loses its identity there loses everything hung off it.
        Minting only when the device brings no id keeps the server the issuer.
        """
        client = self._clients.get(client_id) if client_id else None

        if client is None:
            client = Client(id=client_id or uuid4().hex, role=role or DeviceRole.SCOREBOARD)
            self._clients[client.id] = client
        elif role is not None:
            client.role = role

        return client

    def get(self, client_id: str) -> Client | None:
        return self._clients.get(client_id)


# Module-level singleton store.
store = ClientStore()
