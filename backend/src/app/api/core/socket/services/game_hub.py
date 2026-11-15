"""Per-game WebSocket rooms: the connections of every device in one game, so state
changes reach all of them. Process-local, like the game store.
"""

from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole
from app.api.core.domain.language import Language
from app.api.core.socket.dto.server_message import ServerMessage


@dataclass
class Connection:
    """One device in a room: its socket, and the client it belongs to."""

    websocket: WebSocket
    client: Client
    language: Language = Language.DE
    admin: bool = False
    user_id: str | None = None


class GameHub:
    def __init__(self) -> None:
        # Keyed by socket so a leaving device is found without scanning the room.
        self._rooms: dict[str, dict[WebSocket, Connection]] = {}

    def join(
        self, game_id: str, websocket: WebSocket, client: Client, language: Language = Language.DE
    ) -> Connection:
        connection = Connection(websocket=websocket, client=client, language=language)
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
        """Send to one device of the room by client id; a device that left is skipped."""
        connection = next(
            (c for c in self.connections(game_id) if c.client.id == client_id), None
        )
        if connection is not None:
            await self._deliver(game_id, connection, message.model_dump_json(by_alias=True))

    async def broadcast(
        self, game_id: str, message: ServerMessage, *, role: DeviceRole | None = None
    ) -> None:
        """Push a message to every device in the game's room, or only those with `role`."""
        payload = message.model_dump_json(by_alias=True)
        for connection in self.connections(game_id):
            if role is not None and connection.client.role is not role:
                continue
            await self._deliver(game_id, connection, payload)

    async def _deliver(self, game_id: str, connection: Connection, payload: str) -> None:
        """Send to a connection, removing it from the room if the send fails."""
        try:
            await connection.websocket.send_text(payload)
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            self.leave(game_id, connection.websocket)


hub = GameHub()
