from dataclasses import dataclass

from app.api.core.domain.device_role import DeviceRole


@dataclass
class Client:
    """One device the server has seen, across connections and games.

    A **device**, not a person: the calibration and the reference frame belong
    to one camera in one position, so two phones of the same player are two
    clients. When accounts arrive, a `user_id` joins this record rather than
    replacing the id.

    Holding the role here rather than on the connection is what lets a device
    survive a reload: the reconnect is a new socket, but it carries the same
    client id, so the server can say what this device was.
    """

    id: str
    role: DeviceRole = DeviceRole.SCOREBOARD
