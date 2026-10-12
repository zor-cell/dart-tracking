"""Per-game WebSocket rooms.

A game is played across devices: the phone aimed at the board runs the camera,
further phones join as scoreboards. Their
connections are held together in a room per game so every state change reaches
all of them.

Not everything is broadcast. A reply that belongs to one camera's picture —
`calibration_result` and `detection_result`, whose overlays live in that
camera's pixel grid — goes to its sender alone; only the shared game state is
pushed to the whole room.

Process-local, like the game store: a room spans one worker process.
"""

from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.socket.dto.server_message import ServerMessage


@dataclass(frozen=True)
class Connection:
    """One device in a room: its socket, and which device it is.

    The client outlives the connection and carries the role; the room only says
    who is currently reachable. That split is what makes a reload cheap — the
    socket goes and comes back, the device stays the same.
    """

    websocket: WebSocket
    client: Client


class GameHub:
    def __init__(self) -> None:
        # Keyed by socket so a leaving device is found without scanning the room.
        self._rooms: dict[str, dict[WebSocket, Connection]] = {}

    def join(self, game_id: str, websocket: WebSocket, client: Client) -> Connection:
        connection = Connection(websocket=websocket, client=client)
        self._rooms.setdefault(game_id, {})[websocket] = connection
        return connection

    def leave(self, game_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(game_id)
        if room is None:
            return
        room.pop(websocket, None)
        if not room:
            del self._rooms[game_id]

    def connections(self, game_id: str) -> list[Connection]:
        """Who is currently in the room. A snapshot, safe to iterate while
        connections come and go."""
        return list(self._rooms.get(game_id, {}).values())

    async def send(self, connection: Connection, message: ServerMessage) -> None:
        """Answer one device. Serializing by alias is the wire contract, so it
        lives here rather than at every call site."""
        await connection.websocket.send_text(message.model_dump_json(by_alias=True))

    async def send_to_client(
        self, game_id: str, client_id: str, message: ServerMessage
    ) -> None:
        """Reach one device by name rather than by the connection in hand.

        For a message whose recipient is not the sender: the device that asked
        for a recalibration is not the one that carries it out. A device that
        has since left the room is simply not reached — what it was waiting on
        stopped mattering when it left.
        """
        connection = next(
            (c for c in self.connections(game_id) if c.client.id == client_id), None
        )
        if connection is not None:
            await self._deliver(game_id, connection, message.model_dump_json(by_alias=True))

    async def broadcast(
        self, game_id: str, message: ServerMessage, *, role: DeviceRole | None = None
    ) -> None:
        """Push a message to every device in the game's room.

        `role` narrows it to the devices doing one job — a recalibration request
        concerns the cameras and nobody else.
        """
        payload = message.model_dump_json(by_alias=True)
        for connection in self.connections(game_id):
            if role is not None and connection.client.role is not role:
                continue
            await self._deliver(game_id, connection, payload)

    async def _deliver(self, game_id: str, connection: Connection, payload: str) -> None:
        """Send to a device that is not the one being answered right now.

        A device that dropped without a clean close is only noticed here, when
        the send fails; it is removed from the room so one dead phone cannot
        block the others.
        """
        try:
            await connection.websocket.send_text(payload)
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            self.leave(game_id, connection.websocket)


hub = GameHub()
