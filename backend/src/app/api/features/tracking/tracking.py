import base64
import json

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.services.session_store import store
from app.api.features.tracking.dto.calibration_frame import CalibrationFrameMessage
from app.api.features.tracking.dto.calibration_result import CalibrationResultMessage
from app.api.features.tracking.dto.connection_established import ConnectionEstablishedMessage
from app.api.features.tracking.dto.game_state_message import GameStateMessage
from app.api.features.tracking.dto.throw_frame import ThrowFrameMessage
from app.api.features.tracking.dto.throw_received import ThrowReceivedMessage
from app.api.features.tracking.entity.calibration_failure import CalibrationFailure
from app.api.features.tracking.services.board_detector import detect_board
from app.api.features.tracking.services.calibration_store import store as calibration_store

router = APIRouter(prefix="/ws", tags=["Tracking"])


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
                frame = CalibrationFrameMessage.model_validate(message)
                image = _decode_jpeg(frame.image)

                outcome = (
                    detect_board(image)
                    if image is not None
                    else CalibrationFailure.NO_COLOURED_REGION
                )
                if isinstance(outcome, CalibrationFailure):
                    response = CalibrationResultMessage.failed(outcome)
                else:
                    calibration_store.set(game_id, outcome)
                    response = CalibrationResultMessage.from_calibration(outcome)
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


def _decode_jpeg(encoded: str) -> np.ndarray | None:
    """Base64 JPEG -> BGR image, or None if it will not decode."""
    try:
        buffer = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    except (ValueError, TypeError):
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)