"""The single WebSocket endpoint: dispatches incoming frames to whichever
feature's pipeline handles that message type.

This is core rather than a feature because it does not own any domain logic
itself — it only decodes the wire message and calls into calibration/game/
detection services. Pulling in feature-specific DTOs and services here is the
one deliberate exception to core not depending on features (mirrors the
frontend's core/socket/dto/client-message.ts).
"""

import asyncio
import base64
import logging
from collections.abc import Callable
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
from app.api.features.announcement.domain.announcer import choose_announcer
from app.api.features.announcement.dto.announcer_state import AnnouncerStateDto
from app.api.features.announcement.dto.command.claim_announcer import ClaimAnnouncerDto
from app.api.features.announcement.dto.dart_announcement import DartAnnouncementDto
from app.api.features.announcement.services.announcer_store import store as announcer_store
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.calibration.dto.calibration_requested import (
    CalibrationRequestedDto,
)
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.calibration.dto.calibration_status import CalibrationStatusDto
from app.api.features.calibration.dto.command.request_calibration import (
    RequestCalibrationDto,
)
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.debug.render import (
    write_debug_images as write_calibration_debug_images,
)
from app.api.features.calibration.services.calibration_request_store import (
    store as calibration_request_store,
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
from app.api.features.evaluation.dto.command.set_evaluation import SetEvaluationDto
from app.api.features.evaluation.services import recorder
from app.api.features.game.dto.command.game_command import GameCommand
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.command.next_player import NextPlayerDto
from app.api.features.game.dto.command.register_dart import RegisterDartDto
from app.api.features.game.dto.command.undo import UndoDto
from app.api.features.game.domain.dart import Dart as ScoredDart
from app.api.features.game.domain.game import Game
from app.api.features.game.persistence.game_repository import repository as game_repository
from app.infrastructure import database

router = APIRouter(prefix="/ws", tags=["Tracking"])

logger = logging.getLogger(__name__)

_TESTDATA_ROOT = Path(__file__).resolve().parents[5] / "testdata"
_CALIBRATION_DEBUG_ROOT = _TESTDATA_ROOT / "calibration" / "_socket_debug"
_DETECTION_DEBUG_ROOT = _TESTDATA_ROOT / "detection" / "_socket_debug"

# Both detectors keep their trace in a module global, so two runs at once would
# read each other's. Holds until the trace has been read out.
_detector_lock = asyncio.Lock()

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
    async with database.session_scope() as session:
        game = await game_repository.get(session, game_id)

    if game is None:
        await websocket.close(code=1008)
        return

    client = await client_store.resolve(client_id)

    await websocket.accept()
    connection = hub.join(game_id, websocket, client)
    await hub.send(connection, ClientStateDto.from_entity(client))
    await hub.send(connection, GameStateDto.from_entity(game))
    await _publish_announcer(game_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = client_message_adapter.validate_json(raw)
            except ValidationError as error:
                logger.warning("[socket] ignored malformed message: %s", error)
                continue

            await _dispatch(connection, game_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(game_id, websocket)
        await _publish_announcer(game_id)


async def _dispatch(
    connection: Connection, game_id: str, message: ClientMessage
) -> None:
    """Route one parsed client message to its feature.

    The game itself is not carried along: every handler that changes it reads it
    fresh under a row lock (`_apply`), because a game now outlives the process
    and is shared across connections.

    Frames come from the camera device only; the game commands come from any
    device in the room — the camera phone correcting a misread, a scoreboard
    phone entering the visit by hand. `set_role` is what decides which of the
    two a device is, and so is the one message that changes that answer.

    `request_calibration` is likewise open to any device: it is what a phone
    without a picture of its own has instead of the calibrate button.
    """
    logger.info(
        "[socket] %s from %s (%s)",
        message.type,
        connection.client.id,
        connection.client.role,
    )

    match message:
        case (CalibrationFrameDto() | DetectionFrameDto()) if (
            connection.client.role is not DeviceRole.CAMERA
        ):
            logger.warning(
                "[socket] ignored %s from a %s device",
                message.type,
                connection.client.role,
            )
        case CalibrationFrameDto():
            await _handle_calibration_frame(connection, game_id, message)
        case DetectionFrameDto():
            await _handle_throw_frame(connection, game_id, message)
        case RequestCalibrationDto():
            await _request_calibration(game_id, requester=connection.client.id)
        case SetRoleDto():
            await _handle_client_command(connection, message)
            await _publish_announcer(game_id)
        case ClaimAnnouncerDto():
            await announcer_store.choose(game_id, connection.client.id)
            await _publish_announcer(game_id)
        case SetEvaluationDto():
            await _handle_set_evaluation(game_id, message)
        case RegisterDartDto() | UndoDto() | NextPlayerDto():
            await _handle_game_command(game_id, message)


async def _handle_client_command(connection: Connection, command: ClientCommand) -> None:
    """Record what this device does in the game, and confirm it.

    The confirmation is not redundant with the device having applied the role
    locally: the command is issued on the way into a game, so it reaches the
    server after the handshake already answered with the *previous* role. This
    reply is what settles the two, and it is ordered behind that answer.

    The connection's own copy is updated as well as the store: the room filters
    broadcasts by role off that object (`hub.broadcast(role=...)`).
    """
    match command:
        case SetRoleDto():
            connection.client.role = command.role
            await client_store.save(connection.client)

    await hub.send(connection, ClientStateDto.from_entity(connection.client))


async def _apply(
    game_id: str,
    mutate: Callable[[Game], None],
    record: recorder.Recording | None = None,
) -> tuple[Game, bool] | None:
    """Run one mutation on the game under a row lock: the state afterwards and
    whether anything changed, or None if the game is gone.

    `record` describes what just happened for the evaluation, appended in the
    same transaction so its log cannot drift from the state it records.

    The lock is what makes a visit safe to end twice. The domain relies on
    read-modify-write being uninterrupted — two devices ending the same visit,
    the second finding a fresh empty turn and doing nothing — and that used to
    come free from the event loop holding one shared object. Across
    transactions it does not, so `SELECT … FOR UPDATE` restores it.
    """
    async with database.session_scope() as session:
        game = await game_repository.lock(session, game_id)
        if game is None:
            return None

        at = recorder.position_of(game)
        revision = game.revision
        mutate(game)
        changed = game.revision != revision
        if changed:
            await game_repository.save(session, game)

        if record is not None:
            recorder.append(session, game_id, record(at, changed))

    return game, changed


async def _handle_game_command(game_id: str, command: GameCommand) -> None:
    """Apply one command and push the result to the room.

    A command that changes nothing is not broadcast — a fourth dart in a visit,
    an undo with nothing left to take back, or the second `next_player` when two
    devices ended the same visit at once. The revision is what says whether
    anything happened, and a room full of devices should not be woken for a
    state they already hold.

    Broadcasting happens after the transaction commits, so no device is ever
    shown a state that is not yet durable.
    """
    armed = await recorder.camera_armed(game_id)

    def mutate(game: Game) -> None:
        match command:
            case RegisterDartDto():
                game.register_dart(command.to_entity())
            case UndoDto():
                game.undo()
            case NextPlayerDto():
                game.next_player()

    applied = await _apply(game_id, mutate, recorder.for_command(command, camera_armed=armed))
    if applied is None:
        return

    game, changed = applied
    if not changed:
        return

    if isinstance(command, NextPlayerDto):
        recorder.settle_visit(game)

    await _publish_state(game)
    if isinstance(command, NextPlayerDto):
        await _request_calibration(game.id, requester=None)


async def _handle_set_evaluation(game_id: str, command: SetEvaluationDto) -> None:
    """Mark the game as a test run, or stop. Pushed to the room, so the switch
    reads the same on every device."""
    applied = await _apply(game_id, lambda game: game.set_evaluation(command.enabled))
    if applied is not None and applied[1]:
        await _publish_state(applied[0])


async def _publish_state(game: Game) -> None:
    """Push the authoritative state to every device in the game's room."""
    await hub.broadcast(game.id, GameStateDto.from_entity(game))


async def _current_announcer(game_id: str) -> str | None:
    """The device in the room that speaks booked darts (docs/feature/ansage.md §1)."""
    return choose_announcer(
        [c.client for c in hub.connections(game_id)],
        await announcer_store.chosen(game_id),
        await scoring_camera_store.holder(game_id),
    )


async def _publish_announcer(game_id: str) -> None:
    """Tell the room who the announcer is, after anything that may have changed it."""
    await hub.broadcast(game_id, AnnouncerStateDto(client_id=await _current_announcer(game_id)))


async def _request_calibration(game_id: str, *, requester: str | None) -> None:
    """Ask every camera in the room to calibrate again from a fresh frame.

    Two things ask for this: a device without a camera of its own, and the end
    of a visit. The visit is the interesting one — it is when the darts come out
    of the board, so it is both the moment a fresh empty-board reference frame
    can be taken and the moment the board is most likely to have been knocked.
    Without it the reference still holds the three darts that were pulled, and
    their absence reads as change on the next throw.

    Only the trigger fans out. A `calibration_result` cannot: its overlay lives
    in the pixel grid of the camera that produced it, so every camera answers
    its own.

    `requester` is the device waiting to hear whether it worked, and is `None`
    for the automatic one, where nobody is (see `calibration_request_store`).
    """
    if requester is None:
        await calibration_request_store.clear(game_id)
    else:
        await calibration_request_store.set(game_id, requester)

    await hub.broadcast(game_id, CalibrationRequestedDto(), role=DeviceRole.CAMERA)


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

    If another device asked for this calibration, the outcome also goes to that
    one as `calibration_status`, stripped of the overlay only this camera can
    place. It goes there and nowhere else: the status answers a question, and
    only the device that asked is waiting on it.
    """
    client_id = connection.client.id
    decoded = _decode_jpeg(frame.image)

    if decoded is None:
        outcome: Calibration | CalibrationFailure = CalibrationFailure.INVALID_IMAGE
    else:
        image, raw = decoded
        async with _detector_lock:
            outcome = await asyncio.to_thread(board_detector.detect_board, image)
            if frame.debug:
                _write_calibration_debug(game_id, client_id, outcome)

    if isinstance(outcome, CalibrationFailure):
        response = CalibrationResultDto.failed(outcome)
    else:
        await calibration_store.set(game_id, client_id, outcome)
        detection_store.seed(game_id, client_id, image)
        if await scoring_camera_store.claim(game_id, client_id):
            recorder.remember_frame(game_id, raw)
            await _publish_announcer(game_id)
        response = CalibrationResultDto.from_calibration(outcome)

    await hub.send(connection, response)

    requester = await calibration_request_store.get(game_id)
    if requester is not None and requester != client_id:
        await hub.send_to_client(
            game_id, requester, CalibrationStatusDto.from_result(response)
        )


async def _handle_throw_frame(
    connection: Connection, game_id: str, frame: DetectionFrameDto
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
    decoded = _decode_jpeg(frame.image)
    calibration = await calibration_store.get(game_id, client_id)
    reference = detection_store.get(game_id, client_id)
    empty_board = detection_store.empty_board(game_id, client_id)

    aligned: np.ndarray | None = None
    rejected_miss = False
    metrics: dict[str, float] = {}
    raw = b""

    if decoded is None:
        outcome: Dart | DetectionFailure = DetectionFailure.INVALID_IMAGE
    elif calibration is None or reference is None:
        outcome = DetectionFailure.NOT_CALIBRATED
    else:
        image, raw = decoded
        async with _detector_lock:
            outcome = await asyncio.to_thread(
                dart_detector.detect_dart, reference, image, calibration, empty_board
            )
            if frame.debug:
                _write_detection_debug(game_id, client_id, outcome)
            # Both read under the lock: the trace is a module global that the
            # next run replaces.
            aligned = dart_detector.trace.aligned
            rejected_miss = dart_detector.trace.rejected_miss
            metrics = recorder.metrics_of(dart_detector.trace)
    metrics |= recorder.trigger_metrics_of(frame.trigger)

    scoring = await scoring_camera_store.is_scoring(game_id, client_id)

    if isinstance(outcome, DetectionFailure):
        # A rejected miss or a pulled dart is still a change in the picture; left
        # out of the reference, it would be found again on every later throw.
        absorbed = rejected_miss or outcome is DetectionFailure.DARTS_REMOVED
        if absorbed and aligned is not None:
            detection_store.set(game_id, client_id, aligned)
        await hub.send(connection, DetectionResultDto.failed(outcome))
        if scoring:
            await recorder.note_failure(game_id, client_id, outcome, metrics)
        return

    if aligned is not None:
        detection_store.set(game_id, client_id, aligned)

    await hub.send(connection, DetectionResultDto.detected(outcome, calibration))

    if not scoring:
        return

    # Only located darts: the report labels a series frame by frame against the
    # darts that were booked.
    recorder.note_throw(game_id, raw)

    # The detected segment carries the field, not just the points, so a tracked
    # dart reaches the scoreboard in the same form as a manually entered one.
    # The tip comes along so devices without a camera can draw where it landed.
    dart = ScoredDart(
        value=outcome.segment.value,
        multiplier=outcome.segment.multiplier,
        position=outcome.tip_board,
    )

    applied = await _apply(
        game_id,
        lambda game: game.register_dart(dart),
        recorder.for_detection(dart, client_id, metrics),
    )
    if applied is None:
        return

    # Pushed even when the game absorbed the dart (a trigger during a full
    # visit): the camera trims its drawn outlines against this state.
    game, changed = applied
    await _publish_state(game)

    announcer = await _current_announcer(game_id)
    if changed and announcer is not None:
        await hub.send_to_client(game_id, announcer, DartAnnouncementDto.from_entity(dart, game))



def _write_calibration_debug(
    game_id: str, client_id: str, outcome: Calibration | CalibrationFailure
) -> None:
    """Dump the just-finished board attempt's per-stage images (see scripts/calibration/run_debug.py).

    Split by camera as well as by game, so two cameras filming one board do not
    interleave their stages into a single folder.
    """
    out_dir = _CALIBRATION_DEBUG_ROOT / game_id / client_id / _timestamp()
    written = write_calibration_debug_images(board_detector.trace, outcome, out_dir)
    logger.info("[calibration debug] %d image(s) in %s", len(written), out_dir)


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
    logger.info("[detection debug] %d image(s) in %s", len(written), out_dir)


def _timestamp() -> str:
    """A filesystem-safe UTC stamp, unique per attempt, for a debug subfolder."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")


def _decode_jpeg(encoded: str) -> tuple[np.ndarray, bytes] | None:
    """Base64 JPEG -> the BGR image and the bytes it came from, or None if it
    will not decode. The bytes are kept because a frame the evaluation keeps is
    written back out exactly as the camera sent it."""
    try:
        raw = base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if image is None else (image, raw)