"""Per-game WebSocket rooms.

A game is played across devices: the phone aimed at the board runs the camera,
further phones join as scoreboards (see docs/feature/multi-device.md). Their
connections are held together in a room per game so every state change reaches
all of them.

Not everything is broadcast. A reply that belongs to one camera's picture —
`calibration_result` and `detection_result`, whose overlays live in that
camera's pixel grid — goes to its sender alone; only the shared game state is
pushed to the whole room.

Process-local, like the game store: a room spans one worker process.
"""

from fastapi import WebSocket, WebSocketDisconnect

from app.api.core.socket.dto.server_message import ServerMessage


class GameHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    def join(self, game_id: str, websocket: WebSocket) -> None:
        self._rooms.setdefault(game_id, set()).add(websocket)

    def leave(self, game_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(game_id)
        if room is None:
            return
        room.discard(websocket)
        if not room:
            del self._rooms[game_id]

    async def send(self, websocket: WebSocket, message: ServerMessage) -> None:
        """Answer one client. Serializing by alias is the wire contract, so it
        lives here rather than at every call site."""
        await websocket.send_text(message.model_dump_json(by_alias=True))

    async def broadcast(self, game_id: str, message: ServerMessage) -> None:
        """Push a message to every device in the game's room.

        A device that dropped without a clean close is only noticed here, when
        the send fails; it is removed from the room so one dead phone cannot
        block the others.
        """
        payload = message.model_dump_json(by_alias=True)
        for websocket in list(self._rooms.get(game_id, ())):
            try:
                await websocket.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, ConnectionError):
                self.leave(game_id, websocket)

hub = GameHub()
