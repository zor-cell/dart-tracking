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
from app.api.features.calibration.dto.calibration_result import CalibrationResult
from app.api.features.calibration.entity.calibration import Calibration
from app.api.features.calibration.entity.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.services.calibration_debug import (
    write_debug_images as write_calibration_debug_images,
)
from app.api.features.calibration.services.calibration_store import store as calibration_store
from app.api.features.detection.dto.detection_result import DetectionResult
from app.api.features.detection.dto.detection_frame import ThrowFrameMessage
from app.api.features.detection.entity.detection import Dart
from app.api.features.detection.entity.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from app.api.features.detection.services.detection_debug import (
    write_debug_images as write_detection_debug_images,
)
from app.api.features.detection.services.detection_store import store as detection_store
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.game_state_message import GameStateMessage
from app.api.features.game.entity.game import Game
from app.api.features.game.services.game_store import store as game_store

router = APIRouter(prefix="/ws", tags=["Tracking"])

_TESTDATA_ROOT = Path(__file__).resolve().parents[4] / "testdata"
_CALIBRATION_DEBUG_ROOT = _TESTDATA_ROOT / "calibration" / "_socket_debug"
_DETECTION_DEBUG_ROOT = _TESTDATA_ROOT / "detection" / "_socket_debug"


@router.websocket("/games/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    game = game_store.get(game_id)
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
            elif message.get("type") == "detection_frame":
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
    images.
    """
    frame = CalibrationFrameMessage.model_validate(message)
    image = _decode_jpeg(frame.image)

    outcome = (
        board_detector.detect_board(image)
        if image is not None
        else CalibrationFailure.INVALID_IMAGE
    )
    if frame.debug and image is not None:
        _write_calibration_debug(game_id, outcome)

    if isinstance(outcome, CalibrationFailure):
        response = CalibrationResult.failed(outcome)
    else:
        calibration_store.set(game_id, outcome)
        detection_store.set(game_id, image)
        response = CalibrationResult.from_calibration(outcome)

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
    reference = detection_store.get(game_id)

    if image is None:
        outcome: Dart | DetectionFailure = DetectionFailure.INVALID_IMAGE
    elif calibration is None or reference is None:
        outcome = DetectionFailure.NOT_CALIBRATED
    else:
        outcome = dart_detector.detect_dart(reference, image, calibration)
        if frame.debug:
            _write_detection_debug(game_id, outcome)

    if isinstance(outcome, DetectionFailure):
        await websocket.send_text(
            DetectionResult.failed(outcome).model_dump_json(by_alias=True)
        )
        return

    game.register_dart(outcome.points)
    if dart_detector.trace.aligned is not None:
        detection_store.set(game_id, dart_detector.trace.aligned)

    await websocket.send_text(
        DetectionResult.detected(outcome, calibration).model_dump_json(by_alias=True)
    )
    await websocket.send_text(
        GameStateMessage(state=GameStateDto.from_entity(game)).model_dump_json(by_alias=True)
    )


def _write_calibration_debug(game_id: str, outcome: Calibration | CalibrationFailure) -> None:
    """Dump the just-finished board attempt's per-stage images (see scripts/calibration/run_debug.py)."""
    out_dir = _CALIBRATION_DEBUG_ROOT / game_id / _timestamp()
    written = write_calibration_debug_images(board_detector.trace, outcome, out_dir)
    print(f"[calibration debug] {len(written)} image(s) in {out_dir}")


def _write_detection_debug(game_id: str, outcome: Dart | DetectionFailure) -> None:
    """Dump the just-finished throw's per-stage images (see scripts/detection/run_debug.py)."""
    dart = outcome if isinstance(outcome, Dart) else None
    out_dir = _DETECTION_DEBUG_ROOT / game_id / _timestamp()
    written = write_detection_debug_images(dart_detector.trace, dart, out_dir)
    print(f"[detection debug] {len(written)} image(s) in {out_dir}")


def _timestamp() -> str:
    """A filesystem-safe UTC stamp, unique per attempt, for a debug subfolder."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")


def _decode_jpeg(encoded: str) -> np.ndarray | None:
    """Base64 JPEG -> BGR image, or None if it will not decode."""
    try:
        buffer = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    except (ValueError, TypeError):
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)