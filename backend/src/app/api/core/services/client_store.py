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

    def resolve(self, client_id: str | None) -> Client:
        """The device behind a connection: found, or created on the spot.

        Nothing but the id is asked for. What the device is stays whatever it
        was — the record is the answer to "what am I" after a reload, so a
        connect must not overwrite it. Changing it takes a `set_role` command.

        An id the store does not know is kept rather than replaced. It happens
        whenever the server restarted — which in development is constantly —
        and a device that loses its identity there loses everything hung off it.
        Minting only when the device brings no id keeps the server the issuer.

        A device is a browser profile, not a tab: two tabs share `localStorage`
        and therefore this record, role included.
        """
        client = self._clients.get(client_id) if client_id else None

        if client is None:
            client = Client(id=client_id or uuid4().hex, role=DeviceRole.SCOREBOARD)
            self._clients[client.id] = client

        return client

    def get(self, client_id: str) -> Client | None:
        return self._clients.get(client_id)


# Module-level singleton store.
store = ClientStore()
