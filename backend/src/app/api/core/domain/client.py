from dataclasses import dataclass

from app.api.core.domain.device_role import DeviceRole


@dataclass
class Client:
    """One device the server has seen, across connections and games, with its role.

    Only a `set_role` command changes the role; a reconnect keeps it.
    """

    id: str
    role: DeviceRole = DeviceRole.SCOREBOARD
