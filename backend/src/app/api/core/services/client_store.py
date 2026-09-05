"""Redis-backed store of the devices the server knows.

Survives a restart, expires after a month of silence.
See docs/feature/done/multi-device.md §5.
"""

from uuid import uuid4

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.infrastructure import redis_client

# A device outlives any single game, so it is kept far longer than the
# game-scoped keys.
_TTL_SECONDS = 30 * 24 * 60 * 60


def _key(client_id: str) -> str:
    return f"client:{client_id}:role"


class ClientStore:
    async def resolve(self, client_id: str | None) -> Client:
        """The device behind a connection: found, or created on the spot. An
        unknown id is kept rather than replaced, and the role is left as it was
        — changing it takes a `set_role` command."""
        if client_id:
            # GETEX reads and renews the expiry in one round trip, so a device
            # that keeps connecting never ages out.
            role = await redis_client.client().getex(_key(client_id), ex=_TTL_SECONDS)
            if role is not None:
                return Client(id=client_id, role=DeviceRole(role.decode()))

        client = Client(id=client_id or uuid4().hex, role=DeviceRole.SCOREBOARD)
        await self.save(client)
        return client

    async def save(self, client: Client) -> None:
        """Write the device's role back. Needed because the store no longer
        hands out the object it holds, so mutating it changes nothing."""
        await redis_client.client().set(_key(client.id), client.role, ex=_TTL_SECONDS)


store = ClientStore()
