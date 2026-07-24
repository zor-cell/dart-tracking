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
from app.api.features.detection.dto.dart_detected import DartDetectedMessage
from app.api.features.detection.dto.throw_frame import ThrowFrameMessage
from app.api.features.detection.entity.dart import Dart
from app.api.features.detection.entity.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from app.api.features.detection.services.frame_store import store as frame_store
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_state_message import GameStateMessage
from app.api.features.game.entity.game import Game
from app.api.features.game.services.session_store import store

router = APIRouter(prefix="/ws", tags=["Tracking"])

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
                await _handle_calibration_frame(websocket, game_id, message)
            elif message.get("type") == "throw_frame":
                await _handle_throw_frame(websocket, game, game_id, message)
    except WebSocketDisconnect:
        pass


async def _handle_calibration_frame(websocket: WebSocket, game_id: str, message: dict) -> None:
    """Detect the board in a calibration frame, store the result, and reply.

    On success: store the homography for the game, seed the detection reference
    with this frame — it is the empty board every later throw is first
    differenced against, and it already sits in the pixel grid the homography
    belongs to — and reply with the recognised board. On failure: reply naming
    the stage that gave up. A frame flagged `debug` also dumps its per-stage
    images (see `scripts/debug_images.py`).
    """
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
        frame_store.set(game_id, image)
        response = CalibrationResultMessage.from_calibration(outcome)

    await websocket.send_text(response.model_dump_json(by_alias=True))


async def _handle_throw_frame(
    websocket: WebSocket, game: Game, game_id: str, message: dict
) -> None:
    """Locate the dart in a throw frame, score it, and push the result.

    On a hit: register the dart on the game, roll the reference frame forward to
    the aligned copy — so the next throw is differenced against this one rather
    than the empty board, and darts already in the board cancel out — then send
    the per-throw `dart_detected` feedback followed by the authoritative
    `game_state`. On a failure: send `dart_detected` naming the stage that gave
    up and leave the game untouched.

    Detection needs both the game's calibration and the frame to difference
    against; absent either (no calibration yet, or an undecodable image) it
    reports the matching failure instead of attempting a fit.
    """
    frame = ThrowFrameMessage.model_validate(message)
    image = _decode_jpeg(frame.image)
    calibration = calibration_store.get(game_id)
    reference = frame_store.get(game_id)

    if image is None:
        outcome: Dart | DetectionFailure = DetectionFailure.INVALID_IMAGE
    elif calibration is None or reference is None:
        outcome = DetectionFailure.NOT_CALIBRATED
    else:
        outcome = dart_detector.detect_dart(reference, image, calibration)

    if isinstance(outcome, DetectionFailure):
        await websocket.send_text(
            DartDetectedMessage.failed(outcome).model_dump_json(by_alias=True)
        )
        return

    game.register_dart(outcome.points)
    # This throw is the reference for the next one. The aligned copy, not the raw
    # frame, or the reference drifts out of the calibration's pixel grid.
    if dart_detector.trace.aligned is not None:
        frame_store.set(game_id, dart_detector.trace.aligned)

    await websocket.send_text(
        DartDetectedMessage.detected(outcome).model_dump_json(by_alias=True)
    )
    await websocket.send_text(
        GameStateMessage(state=GameStateDto.from_entity(game)).model_dump_json(by_alias=True)
    )


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