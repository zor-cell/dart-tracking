import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.services.session_store import store
from app.api.features.tracking.dto.calibration_frame import CalibrationFrameMessage
from app.api.features.tracking.dto.calibration_result import CalibrationResultMessage
from app.api.features.tracking.dto.connection_established import ConnectionEstablishedMessage
from app.api.features.tracking.dto.game_state_message import GameStateMessage
from app.api.features.tracking.dto.throw_frame import ThrowFrameMessage
from app.api.features.tracking.dto.throw_received import ThrowReceivedMessage

router = APIRouter(prefix="/ws", tags=["Tracking"])

# Stub homography until real board detection (Hough/contour) is built against
# the Phase 1 test footage — an identity matrix so the wire shape is already final.
_STUB_HOMOGRAPHY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


@router.websocket("/games/{game_id}")
async def dart_tracking_endpoint(websocket: WebSocket, game_id: str) -> None:
    game = store.get(game_id)
    if game is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_text(ConnectionEstablishedMessage().model_dump_json(by_alias=True))
    await websocket.send_text(
        GameStateMessage(state=GameStateDto.from_entity(game)).model_dump_json(by_alias=True)
    )

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)

            if message.get("type") == "calibration_frame":
                CalibrationFrameMessage.model_validate(message)
                response = CalibrationResultMessage(success=True, homography=_STUB_HOMOGRAPHY)
            elif message.get("type") == "throw_frame":
                frame = ThrowFrameMessage.model_validate(message)
                # Stub: once dart localization/scoring is implemented, this is
                # where it plugs in — score the frame, call
                # `game.register_dart(points)`, then push the updated state
                # the same way as right after connecting:
                #   await websocket.send_text(
                #       GameStateMessage(state=GameStateDto.from_entity(game)).model_dump_json(by_alias=True)
                #   )
                response = ThrowReceivedMessage(bytes_received=len(base64.b64decode(frame.image)))
            else:
                continue

            await websocket.send_text(response.model_dump_json(by_alias=True))
    except WebSocketDisconnect:
        pass