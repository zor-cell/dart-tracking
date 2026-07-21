"""The single WebSocket endpoint: dispatches incoming frames to whichever
feature's pipeline handles that message type.

This is core rather than a feature because it does not own any domain logic
itself — it only decodes the wire message and calls into calibration/game/
detection services. Pulling in feature-specific DTOs and services here is the
one deliberate exception to core not depending on features (mirrors the
frontend's core/socket/dto/socket-message.ts).
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.core.dto.connection_established import ConnectionEstablishedMessage
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameMessage
from app.api.features.calibration.dto.calibration_result import CalibrationResultMessage
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.services.board_debug_images import write_debug_images
from app.api.features.calibration.services.calibration_store import store as calibration_store
from app.api.features.detection.dto.throw_frame import ThrowFrameMessage
from app.api.features.detection.dto.throw_received import ThrowReceivedMessage
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_state_message import GameStateMessage
from app.api.features.game.services.session_store import store

router = APIRouter(prefix="/ws", tags=["Tracking"])

# Where a `calibration_frame` with `debug: true` dumps its per-stage images.
# Under testdata/, which is entirely gitignored — this is a local dev aid, not
# something that ships.
_DEBUG_OUTPUT_ROOT = Path(__file__).resolve().parents[4] / "testdata" / "calibration" / "socket_debug"


@router.websocket("/games/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
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
                    board_detector.detect_board(image)
                    if image is not None
                    else CalibrationFailure.INVALID_IMAGE
                )
                if frame.debug and image is not None:
                    _write_debug_images(game_id, outcome)

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


def _write_debug_images(game_id: str, outcome: Calibration | CalibrationFailure) -> None:
    """Dump the just-finished attempt's per-stage images (see scripts/debug_images.py)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    out_dir = _DEBUG_OUTPUT_ROOT / game_id / timestamp
    written = write_debug_images(board_detector.trace, outcome, out_dir)
    print(f"[calibration debug] {len(written)} image(s) in {out_dir}")


def _decode_jpeg(encoded: str) -> np.ndarray | None:
    """Base64 JPEG -> BGR image, or None if it will not decode."""
    try:
        buffer = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    except (ValueError, TypeError):
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)