"""The single WebSocket endpoint: decodes each frame and dispatches it to the
feature (calibration, detection, game) that handles its message type.
"""

import asyncio
import base64
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

import cv2
import numpy as np
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.core.domain.device_role import DeviceRole
from app.api.core.services.client_store import store as client_store
from app.api.core.services.request_language import current_language
from app.api.core.socket.dto.client_state import ClientStateDto
from app.api.core.socket.dto.command.authenticate import AuthenticateDto
from app.api.core.socket.dto.command.client_command import ClientCommand
from app.api.core.socket.dto.command.set_role import SetRoleDto
from app.api.core.socket.dto.client_message import (
    ClientMessage,
    client_message_adapter,
)
from app.api.core.socket.services.game_hub import Connection, hub
from app.api.core.socket.services.jpeg_header import jpeg_size
from app.api.features.announcement.domain.announcer import choose_announcer
from app.api.features.announcement.domain.calls import DartCall, TurnCall
from app.api.features.announcement.dto.announcer_state import AnnouncerStateDto
from app.api.features.announcement.dto.calibration_announcement import (
    CalibrationAnnouncementDto,
)
from app.api.features.announcement.dto.command.claim_announcer import ClaimAnnouncerDto
from app.api.features.announcement.dto.dart_announcement import DartAnnouncementDto
from app.api.features.announcement.dto.turn_announcement import TurnAnnouncementDto
from app.api.features.auth.persistence.user_repository import repository as user_repository
from app.api.features.auth.services import access_tokens
from app.api.features.announcement.services.announcer_store import store as announcer_store
from app.api.features.announcement.services.phrases import (
    calibration_phrase,
    dart_phrases,
    turn_phrase,
)
from app.api.features.announcement.domain.speaker import Speaker
from app.api.features.auth.domain.user import User
from app.api.features.announcement.services.speakers import speaker_for
from app.api.features.announcement.services.speech import speech_store
from app.api.features.calibration.dto.calibration_frame import CalibrationFrameDto
from app.api.features.calibration.dto.calibration_requested import (
    CalibrationRequestedDto,
)
from app.api.features.calibration.dto.calibration_result import CalibrationResultDto
from app.api.features.calibration.dto.calibration_state import CalibrationStateDto
from app.api.features.calibration.dto.command.request_calibration import (
    RequestCalibrationDto,
)
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.calibration.domain.calibration_failure import CalibrationFailure
from app.api.features.calibration.domain.calibration_state import calibration_state
from app.api.features.calibration.domain.camera_angle import camera_angle
from app.api.features.calibration.services import board_detector
from app.api.features.calibration.services.calibration_failure_store import (
    store as calibration_failure_store,
)
from app.api.features.calibration.services.calibration_progress import (
    progress as calibration_progress,
)
from app.api.features.calibration.services.calibration_store import store as calibration_store
from app.api.features.detection.dto.detection_result import DetectionResultDto
from app.api.features.detection.dto.detection_frame import DetectionFrameDto
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services import dart_detector
from app.api.features.detection.services.detection_store import store as detection_store
from app.api.features.detection.services.scoring_camera import store as scoring_camera_store
from app.api.features.evaluation.dto.command.set_evaluation import SetEvaluationDto
from app.api.features.game.dto.command.set_tracking_paused import SetTrackingPausedDto
from app.api.features.evaluation.services import recorder
from app.api.features.game.dto.command.game_command import GameCommand
from app.api.features.game.dto.correction_pending import CorrectionPendingDto
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.command.move_dart import MoveDartDto
from app.api.features.game.dto.command.next_player import NextPlayerDto
from app.api.features.game.dto.command.register_dart import RegisterDartDto
from app.api.features.game.dto.command.remove_dart import RemoveDartDto
from app.api.features.game.dto.command.replace_dart import ReplaceDartDto
from app.api.features.game.dto.command.set_ended import SetEndedDto
from app.api.features.game.dto.command.set_win_confirmed import SetWinConfirmedDto
from app.api.features.game.domain.dart import Dart as ScoredDart
from app.api.features.game.domain.game import Game
from app.api.features.game.persistence.game_repository import repository as game_repository
from app.infrastructure import database
from app.infrastructure.config import get_settings
from app.infrastructure.token_bucket import TokenBucket

router = APIRouter(prefix="/ws", tags=["Tracking"])

logger = logging.getLogger(__name__)

# Both detectors keep their trace in a module global, so two runs at once would
# read each other's. Holds until the trace has been read out.
_detector_lock = asyncio.Lock()

# Games whose next player is called once the scoring camera has answered the
# recalibration, whether it held or not.
_turn_calls: set[str] = set()

# Per connection: messages of any kind, and camera frames (each one a detector run).
_MESSAGES_PER_SECOND, _MESSAGE_BURST = 20, 40
_FRAMES_PER_SECOND, _FRAME_BURST = 2, 6
_MAX_CONNECTIONS_PER_GAME = 8
# Longest side of a frame the decoder accepts, in pixels.
_MAX_FRAME_SIDE = 4096

@router.websocket("/games/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    client_id: str | None = Query(default=None, alias="clientId")
) -> None:
    """Join a game's room as the device named by `clientId`, answering with its role.

    A device that never chose a role counts as a scoreboard.
    """
    if not _origin_allowed(websocket):
        await websocket.close(code=1008)
        return

    async with database.session_scope() as session:
        game = await game_repository.get(session, game_id)

    if game is None or len(hub.connections(game_id)) >= _MAX_CONNECTIONS_PER_GAME:
        await websocket.close(code=1008)
        return

    client = await client_store.resolve(client_id)

    await websocket.accept()
    connection = hub.join(game_id, websocket, client, current_language.get())
    await hub.send(connection, ClientStateDto.from_entity(client))
    await hub.send(connection, GameStateDto.from_entity(game))
    await _publish_announcer(game_id)
    await _publish_calibration_state(game_id)

    # A camera without a calibration for this game cannot detect anything, and
    # only its own frame can produce one. A calibrated one gets its board outline back.
    if client.role is DeviceRole.CAMERA:
        calibration = await calibration_store.get(game_id, client.id)
        await hub.send(
            connection,
            CalibrationRequestedDto()
            if calibration is None
            else CalibrationResultDto.from_calibration(calibration),
        )

    messages = TokenBucket(_MESSAGES_PER_SECOND, _MESSAGE_BURST)
    frames = TokenBucket(_FRAMES_PER_SECOND, _FRAME_BURST)
    throttled = False

    try:
        while True:
            raw = await websocket.receive_text()
            if not messages.take():
                throttled = _note_throttled(connection, throttled)
                continue

            try:
                message = client_message_adapter.validate_json(raw)
            except ValidationError as error:
                logger.warning("[socket] ignored malformed message: %s", error)
                continue

            if isinstance(message, CalibrationFrameDto | DetectionFrameDto) and not frames.take():
                throttled = _note_throttled(connection, throttled)
                continue

            await _dispatch(connection, game_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(game_id, websocket)
        await _publish_announcer(game_id)
        await _publish_calibration_state(game_id)


def _origin_allowed(websocket: WebSocket) -> bool:
    """A browser connecting from another site is refused; clients without an Origin are not browsers."""
    origin = websocket.headers.get("origin")
    if origin is None or origin in get_settings().cors_origins:
        return True
    host = websocket.headers.get("host", "")
    return urlsplit(origin).hostname == urlsplit(f"//{host}").hostname


def _note_throttled(connection: Connection, throttled: bool) -> bool:
    """Log the first dropped message of a connection, not every one."""
    if not throttled:
        logger.warning("[socket] throttling messages from %s", connection.client.id)
    return True


async def _dispatch(
    connection: Connection, game_id: str, message: ClientMessage
) -> None:
    """Route one parsed client message to its feature.

    Frames are taken from the camera device only; commands from any device.
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
            await _request_calibration(game_id)
        case SetRoleDto():
            await _handle_client_command(connection, game_id, message)
            await _publish_announcer(game_id)
        case AuthenticateDto():
            account = await _account(message.access_token)
            connection.admin = account is not None and account.is_admin
            connection.user_id = None if account is None else account.id
        case ClaimAnnouncerDto():
            await announcer_store.choose(game_id, connection.client.id)
            await _publish_announcer(game_id)
        case SetEvaluationDto() if not connection.admin:
            logger.warning("[socket] ignored set_evaluation from a non-admin connection")
        case SetEvaluationDto():
            await _handle_set_evaluation(game_id, message)
        case SetTrackingPausedDto():
            await _handle_set_tracking_paused(game_id, message)
        case SetWinConfirmedDto():
            await _set_win_confirmed(game_id, message.confirmed)
        case SetEndedDto():
            await _set_ended(game_id, message.ended)
        case (
            RegisterDartDto()
            | ReplaceDartDto()
            | MoveDartDto()
            | RemoveDartDto()
            | NextPlayerDto()
        ):
            await _handle_game_command(connection, game_id, message)


async def _account(access_token: str) -> User | None:
    """The account a valid token belongs to."""
    user_id = access_tokens.read_subject(access_token)
    if user_id is None:
        return None
    async with database.session_scope() as session:
        return await user_repository.get(session, user_id)


async def _handle_client_command(
    connection: Connection, game_id: str, command: ClientCommand
) -> None:
    """Record what this device does in the game, in the store and on the connection,
    and confirm it.
    """
    match command:
        case SetRoleDto():
            connection.client.role = command.role
            await client_store.save(connection.client)
            client_id = connection.client.id
            if command.role is not DeviceRole.CAMERA and await scoring_camera_store.is_scoring(
                game_id, client_id
            ):
                await scoring_camera_store.release(game_id, client_id)
                await calibration_failure_store.clear(game_id)
            await _publish_calibration_state(game_id)

    await hub.send(connection, ClientStateDto.from_entity(connection.client))


async def _apply(
    game_id: str,
    mutate: Callable[[Game], None],
    record: recorder.Recording | None = None,
) -> tuple[Game, bool] | None:
    """Run one mutation on the game under a row lock and append `record` in the same
    transaction; returns the state and whether it changed, or None if the game is gone.
    """
    async with database.session_scope() as session:
        game = await game_repository.lock(session, game_id)
        if game is None:
            return None

        at = recorder.position_of(game)
        revision = game.revision
        shadows = list(game.shadow_darts)
        mutate(game)
        changed = game.revision != revision
        # Read before stamping, which swaps the booked darts for dated copies.
        placed = [dart for dart in shadows if any(dart is own for own in game.current_turn.darts)]
        if changed:
            game.stamp(datetime.now(UTC))
            await game_repository.save(session, game)

        if record is not None:
            recorder.append(session, game_id, record(at, changed))
        booked = recorder.position_of(game)
        for dart in placed:
            recorder.append(session, game_id, recorder.for_shadow_booking(dart, booked))

    return game, changed


async def _handle_game_command(
    connection: Connection, game_id: str, command: GameCommand
) -> None:
    """Apply one command and, once committed, push the result to the room. A
    correction whose consequence awaits confirmation goes back to its sender only.

    A command that leaves the revision unchanged is not broadcast.
    """
    armed = await recorder.camera_armed(game_id)
    filled = 0
    reset_before: set[int] = set()
    pending: CorrectionPendingDto | None = None
    # Whether the command changed the open visit rather than a closed one.
    open_visit = True

    def mutate(game: Game) -> None:
        nonlocal filled, reset_before, pending, open_visit
        reset_before = game.just_reset()
        if not command.is_current(game):
            logger.info("[socket] refused %s made against an outdated visit", command.type)
            return
        consequence = None
        if isinstance(command, ReplaceDartDto | MoveDartDto | RemoveDartDto):
            open_visit = command.turn is None or command.turn >= len(game.turns) - 1
        match command:
            case RegisterDartDto():
                game.add_dart(command.to_entity())
            case ReplaceDartDto():
                consequence = game.replace_dart(
                    command.index, command.to_entity(), command.turn, command.confirmed
                )
            case MoveDartDto():
                consequence = game.move_dart(
                    command.index, command.to_index, command.turn, command.confirmed
                )
            case RemoveDartDto():
                consequence = game.remove_dart(command.index, command.turn, command.confirmed)
            case NextPlayerDto():
                filled = game.next_player()
        if consequence is not None and isinstance(command, ReplaceDartDto | MoveDartDto | RemoveDartDto):
            pending = CorrectionPendingDto.from_entity(consequence, game, command)

    if isinstance(command, NextPlayerDto):
        handover = recorder.for_handover(None, camera_armed=armed)
        record: recorder.Recording = lambda at, changed: handover(at, changed, filled)
    else:
        record = recorder.for_command(command, camera_armed=armed)
    applied = await _apply(game_id, mutate, record)
    if applied is None:
        return

    game, changed = applied
    if pending is not None:
        await hub.send(connection, pending)
    if not changed:
        return

    if isinstance(command, NextPlayerDto):
        await _end_visit(game)
        return
    await recorder.settle_win(game)

    await _publish_state(game)
    if open_visit and isinstance(command, RegisterDartDto | ReplaceDartDto):
        index = command.index if isinstance(command, ReplaceDartDto) else -1
        await _announce(game, command.to_entity(), game.just_reset() - reset_before, index)


async def _handle_set_evaluation(game_id: str, command: SetEvaluationDto) -> None:
    """Mark the game as a test run, or stop. Pushed to the room, so the switch
    reads the same on every device."""
    applied = await _apply(game_id, lambda game: game.set_evaluation(command.enabled))
    if applied is not None and applied[1]:
        await _publish_state(applied[0])


async def _handle_set_tracking_paused(game_id: str, command: SetTrackingPausedDto) -> None:
    """Pause or resume the camera for the whole room. Resuming recalibrates, so
    darts pulled or the board knocked during the pause do not read as a throw."""
    applied = await _apply(game_id, lambda game: game.set_tracking_paused(command.paused))
    if applied is None or not applied[1]:
        return
    await _publish_state(applied[0])
    if not command.paused:
        await _request_calibration(game_id)


async def _set_win_confirmed(game_id: str, confirmed: bool) -> None:
    """Take the win for the whole room, or go back to it; pushed so every device follows."""
    applied = await _apply(game_id, lambda game: game.set_win_confirmed(confirmed))
    if applied is not None and applied[1]:
        await _publish_state(applied[0])


async def _set_ended(game_id: str, ended: bool) -> None:
    """End a game nobody wins for the whole room, or go back into it."""
    applied = await _apply(game_id, lambda game: game.set_ended(ended))
    if applied is not None and applied[1]:
        await _publish_state(applied[0])


async def _publish_state(game: Game) -> None:
    """Push the authoritative state to every device in the game's room."""
    await hub.broadcast(game.id, GameStateDto.from_entity(game))


async def _current_announcer(game_id: str) -> str | None:
    """The device in the room that speaks booked darts."""
    return choose_announcer(
        [c.client for c in hub.connections(game_id)],
        await announcer_store.chosen(game_id),
        await scoring_camera_store.holder(game_id),
    )


async def _announcer(game_id: str) -> tuple[Connection, Speaker] | None:
    """The announcer's connection, and who it speaks as."""
    announcer = await _current_announcer(game_id)
    connection = next((c for c in hub.connections(game_id) if c.client.id == announcer), None)
    if connection is None:
        return None
    return connection, await speaker_for(connection.user_id, connection.language)


async def _announce(game: Game, dart: ScoredDart, eliminated: set[int], index: int = -1) -> None:
    """Have the room's announcer speak the dart booked at `index` of the open visit."""
    if (found := await _announcer(game.id)) is not None:
        announcer, speaker = found
        call = DartCall.of(dart, game, eliminated, index)
        clips = await speech_store().urls(dart_phrases(call, speaker.language), speaker)
        await hub.send_to_client(
            game.id, announcer.client.id, DartAnnouncementDto.from_entity(call, clips)
        )


async def _announce_calibration(game_id: str, calibrated: bool) -> None:
    """Have the room's announcer say that the calibration failed, or holds again."""
    if (found := await _announcer(game_id)) is not None:
        announcer, speaker = found
        phrase = calibration_phrase(calibrated, speaker.language)
        clips = await speech_store().urls([phrase], speaker)
        await hub.send_to_client(
            game_id,
            announcer.client.id,
            CalibrationAnnouncementDto(calibrated=calibrated, clips=clips),
        )


async def _call_turn(game: Game) -> None:
    """Have the room's announcer call the next player, while their visit is still empty."""
    if game.over or game.current_turn.darts:
        return
    if (found := await _announcer(game.id)) is not None:
        announcer, speaker = found
        call = TurnCall.of(game)
        clips = await speech_store().urls([turn_phrase(call, speaker.language)], speaker)
        await hub.send_to_client(
            game.id, announcer.client.id, TurnAnnouncementDto.from_entity(call, clips)
        )


async def _publish_announcer(game_id: str) -> None:
    """Tell the room who the announcer is, after anything that may have changed it."""
    await hub.broadcast(game_id, AnnouncerStateDto(client_id=await _current_announcer(game_id)))


async def _publish_calibration_state(game_id: str) -> None:
    """Tell the room how far the board calibration is, after anything that may have changed it."""
    cameras = {
        c.client.id for c in hub.connections(game_id) if c.client.role is DeviceRole.CAMERA
    }
    state = calibration_state(
        camera_connected=bool(cameras),
        scoring_connected=await scoring_camera_store.holder(game_id) in cameras,
        calibrating=calibration_progress.running(game_id),
        failed=await calibration_failure_store.failed(game_id),
    )
    await hub.broadcast(game_id, CalibrationStateDto(state=state))


async def _start_calibrating(game_id: str) -> None:
    """Mark an attempt as running; the room hears when it starts and when it times out."""
    if calibration_progress.start(game_id, lambda: _publish_calibration_state(game_id)):
        await _publish_calibration_state(game_id)


async def _request_calibration(game_id: str) -> bool:
    """Ask every camera in the room to calibrate again from a fresh frame.

    Returns whether the room has a camera to ask.
    """
    if not any(c.client.role is DeviceRole.CAMERA for c in hub.connections(game_id)):
        return False
    await _start_calibrating(game_id)
    await hub.broadcast(game_id, CalibrationRequestedDto(), role=DeviceRole.CAMERA)
    return True


async def _handle_calibration_frame(
    connection: Connection, game_id: str, frame: CalibrationFrameDto
) -> None:
    """Detect the board in a calibration frame, store it for this camera, and reply.

    A success seeds the camera's reference frame and claims the scoring role.
    """
    client_id = connection.client.id
    holder = await scoring_camera_store.holder(game_id)
    decides = holder in (None, client_id)
    opens_game = False
    failed_before = decides and await calibration_failure_store.failed(game_id)
    if decides:
        await _start_calibrating(game_id)
    decoded = await asyncio.to_thread(_decode_jpeg, frame.image)

    if decoded is None:
        outcome: Calibration | CalibrationFailure = CalibrationFailure.INVALID_IMAGE
    else:
        image, raw = decoded
        async with _detector_lock:
            outcome = await asyncio.to_thread(board_detector.detect_board, image)

    if isinstance(outcome, CalibrationFailure):
        response = CalibrationResultDto.failed(outcome)
        if decoded is not None:
            await recorder.keep_failed_calibration(game_id, decoded[1], outcome)
        if decides:
            await calibration_failure_store.set(game_id)
    else:
        await calibration_store.set(game_id, client_id, outcome)
        detection_store.seed(game_id, client_id, image)
        if await scoring_camera_store.claim(game_id, client_id):
            opens_game = holder is None
            recorder.remember_frame(game_id, raw)
            angle = camera_angle(outcome)
            if angle is not None:
                await recorder.note_calibration(game_id, client_id, angle)
            await calibration_failure_store.clear(game_id)
            await _publish_announcer(game_id)
        response = CalibrationResultDto.from_calibration(outcome)

    await hub.send(connection, response)

    if decides:
        calibration_progress.finish(game_id)
        await _publish_calibration_state(game_id)
        if failed_before != await calibration_failure_store.failed(game_id):
            await _announce_calibration(game_id, calibrated=failed_before)

    if decides and (game_id in _turn_calls or opens_game):
        handover = game_id in _turn_calls
        _turn_calls.discard(game_id)
        async with database.session_scope() as session:
            game = await game_repository.get(session, game_id)
        # The first claim on a game nobody has thrown in yet calls its opening player.
        if game is not None and (handover or len(game.turns) == 1):
            await _call_turn(game)


async def _handle_throw_frame(
    connection: Connection, game_id: str, frame: DetectionFrameDto
) -> None:
    """Locate the dart in a throw frame, score it, and push the result.

    Every camera rolls its reference forward; only the scoring camera books the dart.
    """
    client_id = connection.client.id
    decoded = await asyncio.to_thread(_decode_jpeg, frame.image)
    calibration = await calibration_store.get(game_id, client_id)
    reference = detection_store.get(game_id, client_id)
    empty_board = detection_store.empty_board(game_id, client_id)

    aligned: np.ndarray | None = None
    blob: np.ndarray | None = None
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
            # Both read under the lock: the trace is a module global that the
            # next run replaces.
            aligned = dart_detector.trace.aligned
            blob = dart_detector.trace.blob
            metrics = recorder.metrics_of(dart_detector.trace)
    metrics |= recorder.trigger_metrics_of(frame.trigger)

    scoring = await scoring_camera_store.is_scoring(game_id, client_id)

    if isinstance(outcome, DetectionFailure):
        if outcome.moves_reference and aligned is not None:
            detection_store.set(game_id, client_id, aligned)
            if scoring:
                recorder.note_absorbed(game_id, raw, frame.trigger)
        await hub.send(connection, DetectionResultDto.failed(outcome))
        if scoring:
            await recorder.note_failure(game_id, client_id, outcome, metrics)
        if scoring and frame.advance_on_pull and (
            await _darts_pulled(game_id, client_id, aligned, empty_board)
        ):
            await _clear_board(game_id, client_id)
        return

    if aligned is not None:
        detection_store.set(game_id, client_id, aligned)
    if blob is not None:
        detection_store.add_dart(game_id, client_id, blob)

    await hub.send(connection, DetectionResultDto.detected(outcome, calibration))

    if not scoring:
        return

    # The dart carries its field and tip, the same form as a manually entered one.
    dart = ScoredDart(
        value=outcome.segment.value,
        multiplier=outcome.segment.multiplier,
        position=outcome.tip_board,
    )

    booked = False
    reset_before: set[int] = set()

    def mutate(game: Game) -> None:
        nonlocal booked, reset_before
        reset_before = game.just_reset()
        booked = game.register_dart(dart)

    record = recorder.for_detection(dart, client_id, metrics)
    applied = await _apply(game_id, mutate, lambda at, _: record(at, booked))
    if applied is None:
        return

    # Pushed even when the game absorbed the dart (a trigger during a full
    # visit): the camera trims its drawn outlines against this state.
    game, _ = applied
    recorder.note_throw(game_id, raw, frame.trigger, booked=booked)
    await recorder.settle_win(game)
    await _publish_state(game)

    if booked:
        await _announce(game, dart, game.just_reset() - reset_before)


async def _darts_pulled(
    game_id: str, client_id: str, aligned: np.ndarray | None, empty_board: np.ndarray | None
) -> bool:
    """Whether every dart this camera located in the visit is out of the board again."""
    if aligned is None or empty_board is None:
        return False
    return await asyncio.to_thread(
        dart_detector.darts_pulled, detection_store.darts(game_id, client_id), aligned, empty_board
    )


async def _clear_board(game_id: str, client_id: str) -> None:
    """Hand over because the visit's darts were pulled, the ones never found booked
    as misses. After the winning visit there is no handover: the room takes the win."""
    filled = 0

    def mutate(game: Game) -> None:
        nonlocal filled
        filled = game.next_player()

    handover = recorder.for_handover(client_id, camera_armed=True)
    applied = await _apply(
        game_id, mutate, lambda at, changed: handover(at, changed, filled) if changed else None
    )
    if applied is None:
        return
    game, changed = applied
    if changed:
        await _end_visit(game)
    elif game.winner is not None:
        await _set_win_confirmed(game_id, True)


async def _end_visit(game: Game) -> None:
    """Push a handover to the room and start the next visit from a fresh empty board."""
    await recorder.settle_visit(game)
    detection_store.end_visit(game.id)
    await _publish_state(game)
    if await _request_calibration(game.id):
        _turn_calls.add(game.id)
    else:
        await _call_turn(game)


def _decode_jpeg(encoded: str) -> tuple[np.ndarray, bytes] | None:
    """Base64 JPEG -> the BGR image and the bytes it came from, or None if it
    will not decode. The bytes are kept because a frame the evaluation keeps is
    written back out exactly as the camera sent it."""
    try:
        raw = base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None
    size = jpeg_size(raw)
    if size is None or max(size) > _MAX_FRAME_SIDE or min(size) == 0:
        return None
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if image is None else (image, raw)