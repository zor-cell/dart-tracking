"""The single WebSocket endpoint: dispatches incoming frames to whichever
feature's pipeline handles that message type.

This is core rather than a feature because it does not own any domain logic
itself — it only decodes the wire message and calls into calibration/game/
detection services. Pulling in feature-specific DTOs and services here is the
one deliberate exception to core not depending on features (mirrors the
frontend's core/socket/dto/socket-message.ts).
"""

import base64
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.core.domain.device_role import DeviceRole
from app.api.core.services.client_store import store as client_store
from app.api.core.socket.dto.client_state import ClientStateDto
from app.api.core.socket.dto.command.client_command import ClientCommand
from app.api.core.socket.dto.command.set_role import SetRoleDto
from app.api.core.socket.dto.client_message import (
    ClientMessage,
    client_message_adapter,
)
from app.api.core.socket.services.game_hub import Connection, hub
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.debug.render import (
    write_debug_images as write_calibration_debug_images,
)
from app.api.features.calibration.services.calibration_store import store as calibration_store
from app.api.features.detection.dto.detection_result import DetectionResultDto
from app.api.features.detection.dto.detection_frame import DetectionFrameDto
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from app.api.features.detection.debug.render import (
    write_debug_images as write_detection_debug_images,
)
from app.api.features.detection.services.detection_store import store as detection_store
from app.api.features.detection.services.scoring_camera import store as scoring_camera_store
from app.api.features.game.dto.command.game_command import GameCommand
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.command.next_player import NextPlayerDto
from app.api.features.game.dto.command.register_dart import RegisterDartDto
from app.api.features.game.dto.command.undo import UndoDto
from app.api.features.game.domain.dart import Dart as ScoredDart
from app.api.features.game.domain.game import Game
from app.api.features.game.services.game_store import store as game_store

router = APIRouter(prefix="/ws", tags=["Tracking"])

_TESTDATA_ROOT = Path(__file__).resolve().parents[4] / "testdata"
_CALIBRATION_DEBUG_ROOT = _TESTDATA_ROOT / "calibration" / "_socket_debug"
_DETECTION_DEBUG_ROOT = _TESTDATA_ROOT / "detection" / "_socket_debug"


@router.websocket("/games/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    client_id: str | None = Query(default=None, alias="clientId")
) -> None:
    """Join a game's room as a known device.

    `clientId` is the whole handshake, and is missing only on a device's first
    ever connect. Everything else the server knows about the device hangs off
    that id — the role included, which is why the connect answers it instead of
    asking for it (`client_state`). Changing it is a `set_role` command.

    A device that has never said otherwise counts as a scoreboard, so a
    forgotten role costs a picture, never a wrong one.
    """
    game = game_store.get(game_id)
    if game is None:
        await websocket.close(code=1008)
        return

    client = client_store.resolve(client_id)

    await websocket.accept()
    connection = hub.join(game_id, websocket, client)
    await hub.send(connection, ClientStateDto.from_entity(client))
    await hub.send(connection, GameStateDto.from_entity(game))

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = client_message_adapter.validate_json(raw)
            except ValidationError as error:
                print(f"[socket] ignored message: {error}")
                continue

            await _dispatch(connection, game, game_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(game_id, websocket)


async def _dispatch(
    connection: Connection, game: Game, game_id: str, message: ClientMessage
) -> None:
    """Route one parsed client message to its feature.

    Frames come from the camera device only; the game commands come from any
    device in the room — the camera phone correcting a misread, a scoreboard
    phone entering the visit by hand. `set_role` is what decides which of the
    two a device is, and so is the one message that changes that answer.
    """
    match message:
        case (CalibrationFrameDto() | DetectionFrameDto()) if (
            connection.client.role is not DeviceRole.CAMERA
        ):
            print(f"[socket] ignored {message.type} from a {connection.client.role} device")
        case CalibrationFrameDto():
            await _handle_calibration_frame(connection, game_id, message)
        case DetectionFrameDto():
            await _handle_throw_frame(connection, game, game_id, message)
        case SetRoleDto():
            await _handle_client_command(connection, message)
        case RegisterDartDto() | UndoDto() | NextPlayerDto():
            await _handle_game_command(game, message)


async def _handle_client_command(connection: Connection, command: ClientCommand) -> None:
    """Record what this device does in the game, and confirm it.

    The confirmation is not redundant with the device having applied the role
    locally: the command is issued on the way into a game, so it reaches the
    server after the handshake already answered with the *previous* role. This
    reply is what settles the two, and it is ordered behind that answer.
    """
    match command:
        case SetRoleDto():
            connection.client.role = command.role

    await hub.send(connection, ClientStateDto.from_entity(connection.client))


async def _handle_game_command(game: Game, command: GameCommand) -> None:
    """Apply one command and push the result to the room.

    A command that changes nothing is not broadcast — a fourth dart in a visit,
    an undo with nothing left to take back, or the second `next_player` when two
    devices ended the same visit at once. The revision is what says whether
    anything happened, and a room full of devices should not be woken for a
    state they already hold.
    """
    revision = game.revision

    match command:
        case RegisterDartDto():
            game.register_dart(command.to_entity())
        case UndoDto():
            game.undo()
        case NextPlayerDto():
            game.next_player()

    if game.revision != revision:
        await _publish_state(game)


async def _publish_state(game: Game) -> None:
    """Push the authoritative state to every device in the game's room."""
    await hub.broadcast(game.id, GameStateDto.from_entity(game))


async def _handle_calibration_frame(
    connection: Connection, game_id: str, frame: CalibrationFrameDto
) -> None:
    """Detect the board in a calibration frame, store the result, and reply.

    On success: store the homography for this camera, seed its detection
    reference with this frame — it is the empty board every later throw is first
    differenced against, and it already sits in the pixel grid the homography
    belongs to — and reply with the recognised board. On failure: reply naming
    the stage that gave up. A frame flagged `debug` also dumps its per-stage
    images.

    Both are kept per camera, not per game: a second camera films the same board
    through a different homography, so it needs its own of each.

    A successful calibration is also where a camera claims the scoring role, it
    being the first point at which it could detect anything. Only the first
    claim takes (see `scoring_camera`).
    """
    client_id = connection.client.id
    image = _decode_jpeg(frame.image)

    outcome = (
        board_detector.detect_board(image)
        if image is not None
        else CalibrationFailure.INVALID_IMAGE
    )
    if frame.debug and image is not None:
        _write_calibration_debug(game_id, client_id, outcome)

    if isinstance(outcome, CalibrationFailure):
        response = CalibrationResultDto.failed(outcome)
    else:
        calibration_store.set(game_id, client_id, outcome)
        detection_store.set(game_id, client_id, image)
        scoring_camera_store.claim(game_id, client_id)
        response = CalibrationResultDto.from_calibration(outcome)

    await hub.send(connection, response)


async def _handle_throw_frame(
    connection: Connection, game: Game, game_id: str, frame: DetectionFrameDto
) -> None:
    """Locate the dart in a throw frame, score it, and push the result.

    On a hit: roll this camera's reference frame forward to the aligned copy —
    so its next throw is differenced against this one rather than the empty
    board, and darts already in the board cancel out — send the per-throw
    `dart_detected` feedback, and, if this is the game's scoring camera,
    register the dart and push the authoritative `game_state`. On a failure:
    send `dart_detected` naming the stage that gave up and leave the game
    untouched.

    The feedback goes to this camera alone (its overlay is in this camera's
    pixel grid), the game state to every device in the room.

    **Only one camera books.** Every camera that saw the throw would otherwise
    register it, and the visit would fill at twice the rate without anything
    reporting an error (see `scoring_camera`). The others still detect in full:
    that is what produces two independent readings of one throw, and what a
    later fusion would be built on. Rolling the reference forward is likewise
    every camera's own business — skipping it for an observer would leave it
    differencing against a board that has since gained darts.

    Detection needs both this camera's calibration and its frame to difference
    against; absent either (not calibrated yet, or an undecodable image) it
    reports the matching failure instead of attempting a fit.
    """
    client_id = connection.client.id
    image = _decode_jpeg(frame.image)
    calibration = calibration_store.get(game_id, client_id)
    reference = detection_store.get(game_id, client_id)

    if image is None:
        outcome: Dart | DetectionFailure = DetectionFailure.INVALID_IMAGE
    elif calibration is None or reference is None:
        outcome = DetectionFailure.NOT_CALIBRATED
    else:
        outcome = dart_detector.detect_dart(reference, image, calibration)
        if frame.debug:
            _write_detection_debug(game_id, client_id, outcome)

    if isinstance(outcome, DetectionFailure):
        await hub.send(connection, DetectionResultDto.failed(outcome))
        return

    if dart_detector.trace.aligned is not None:
        detection_store.set(game_id, client_id, dart_detector.trace.aligned)

    await hub.send(connection, DetectionResultDto.detected(outcome, calibration))

    if not scoring_camera_store.is_scoring(game_id, client_id):
        return

    # The detected segment carries the field, not just the points, so a tracked
    # dart reaches the scoreboard in the same form as a manually entered one.
    # The tip comes along so devices without a camera can draw where it landed.
    game.register_dart(
        ScoredDart(
            value=outcome.segment.value,
            multiplier=outcome.segment.multiplier,
            position=outcome.tip_board,
        )
    )
    # Pushed even when the game absorbed the dart (a trigger during a full
    # visit): the camera trims its drawn outlines against this state.
    await _publish_state(game)


def _write_calibration_debug(
    game_id: str, client_id: str, outcome: Calibration | CalibrationFailure
) -> None:
    """Dump the just-finished board attempt's per-stage images (see scripts/calibration/run_debug.py).

    Split by camera as well as by game, so two cameras filming one board do not
    interleave their stages into a single folder.
    """
    out_dir = _CALIBRATION_DEBUG_ROOT / game_id / client_id / _timestamp()
    written = write_calibration_debug_images(board_detector.trace, outcome, out_dir)
    print(f"[calibration debug] {len(written)} image(s) in {out_dir}")


def _write_detection_debug(
    game_id: str, client_id: str, outcome: Dart | DetectionFailure
) -> None:
    """Dump the just-finished throw's per-stage images (see scripts/detection/run_debug.py).

    Split by camera as well as by game — with two of them running, one throw
    leaves two traces, and telling them apart is the point.
    """
    dart = outcome if isinstance(outcome, Dart) else None
    out_dir = _DETECTION_DEBUG_ROOT / game_id / client_id / _timestamp()
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