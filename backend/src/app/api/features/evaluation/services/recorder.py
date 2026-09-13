"""Everything the socket does for the evaluation, behind one door.

Cross-feature by nature — measuring the tracker means reading the game's
commands and the detector's trace — which is exactly why it lives here and not
in the socket (docs/feature/auswertung.md §2).
"""

import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.socket.services.game_hub import hub
from app.api.features.detection.debug.trace import DetectionTrace
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.dto.throw_trigger import ThrowTriggerDto
from app.api.features.detection.services.scoring_camera import (
    store as scoring_camera_store,
)
from app.api.features.evaluation.domain.game_event import (
    GameEvent,
    GameEventKind,
    VisitPosition,
)
from app.api.features.evaluation.persistence.evaluation_repository import (
    repository as events,
)
from app.api.features.evaluation.services.frame_buffer import store as frames
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.dto.command.game_command import GameCommand
from app.api.features.game.dto.command.next_player import NextPlayerDto
from app.api.features.game.dto.command.register_dart import RegisterDartDto
from app.api.features.game.dto.command.undo import UndoDto
from app.api.features.game.persistence.game_repository import repository as game_repository
from app.infrastructure import database

logger = logging.getLogger(__name__)

# Which kind of event a game command leaves behind.
_KINDS = {
    RegisterDartDto: GameEventKind.MANUAL,
    UndoDto: GameEventKind.UNDO,
    NextPlayerDto: GameEventKind.NEXT_PLAYER,
}

# Failures worth keeping: the ones the fit itself reached. An undecodable frame
# or a missing calibration says nothing about tracking.
_FIT_FAILURES = frozenset(
    {
        DetectionFailure.ALIGNMENT_FAILED,
        DetectionFailure.NO_CHANGE,
        DetectionFailure.IMPLAUSIBLE_SHAPE,
        DetectionFailure.DARTS_REMOVED,
    }
)

# What a caller hands to the game's write step: the event describing a change,
# given where the game stood before it and whether it was taken.
type Recording = Callable[[VisitPosition, bool], GameEvent | None]


def position_of(game: Game) -> VisitPosition:
    """Which visit is open, read before a command moves it on."""
    return VisitPosition(
        turn_index=len(game.turns) - 1, player_index=game.current_player_index
    )


def append(session: AsyncSession, game_id: str, event: GameEvent | None) -> None:
    """Queue an event in the transaction that carries the change it describes."""
    if event is not None:
        events.append(session, game_id, event)


def for_command(command: GameCommand, *, camera_armed: bool) -> Recording:
    """The event one game command leaves behind."""

    def record(at: VisitPosition, accepted: bool) -> GameEvent:
        booked = command if isinstance(command, RegisterDartDto) else None
        return GameEvent(
            kind=_KINDS[type(command)],
            turn_index=at.turn_index,
            player_index=at.player_index,
            accepted=accepted,
            camera_armed=camera_armed,
            value=booked.value if booked else None,
            multiplier=booked.multiplier if booked else None,
        )

    return record


def for_detection(dart: Dart, client_id: str, metrics: dict[str, float]) -> Recording:
    """The event one located throw leaves behind."""

    def record(at: VisitPosition, accepted: bool) -> GameEvent:
        return GameEvent(
            kind=GameEventKind.DETECTED,
            turn_index=at.turn_index,
            player_index=at.player_index,
            accepted=accepted,
            camera_armed=True,
            client_id=client_id,
            value=dart.value,
            multiplier=dart.multiplier,
            position=dart.position,
            metrics=metrics,
        )

    return record


def metrics_of(trace: DetectionTrace) -> dict[str, float]:
    """Detector figures worth keeping per throw: how the dart arrived, how big
    it was, how far the camera had moved (docs/feature/erkennung.md §4)."""
    figures = {
        "fragment_count": trace.fragment_count,
        "largest_fragment_share": round(trace.largest_fragment_share, 4),
        "anchor_to_tip_mm": round(trace.anchor_to_tip_mm, 2),
        "dart_length_mm": round(trace.dart_length_mm, 2),
        "dart_width_mm": round(trace.dart_width_mm, 2),
        "dart_area_mm2": round(trace.dart_area_mm2, 2),
        "changed_from_empty": round(trace.changed_from_empty, 4),
        "alignment_shift_px": round(trace.alignment_shift_px, 2),
        "alignment_inliers": trace.alignment_inliers,
        "region_clipped": round(trace.region_clipped, 4),
        "pixels_per_mm": round(trace.pixels_per_mm, 4),
    }
    # Coerced because these ride into JSONB in the same transaction as the
    # throw: a numpy scalar slipping in would not fail the log, it would roll
    # the dart back.
    return {name: float(value) for name, value in figures.items()}


def trigger_metrics_of(trigger: ThrowTriggerDto | None) -> dict[str, float]:
    """The client's trigger figures, prefixed so they sit apart from the detector's."""
    if trigger is None:
        return {}
    return {f"trigger_{name}": float(value) for name, value in trigger.model_dump().items()}


async def camera_armed(game_id: str) -> bool:
    """Whether the camera that books this game's throws is in the room — what
    separates a visit the tracker missed entirely from one nobody filmed."""
    holder = await scoring_camera_store.holder(game_id)
    return holder is not None and any(
        connection.client.id == holder for connection in hub.connections(game_id)
    )


async def note_failure(
    game_id: str, client_id: str, failure: DetectionFailure, metrics: dict[str, float]
) -> None:
    """Note that the scoring camera looked and came back empty-handed.

    Its own transaction: nothing changed about the game, so there is none to
    join, and a lost measurement must not cost a throw.
    """
    if failure not in _FIT_FAILURES:
        return

    try:
        async with database.session_scope() as session:
            game = await game_repository.get(session, game_id)
            if game is None:
                return
            at = position_of(game)
            events.append(
                session,
                game_id,
                GameEvent(
                    kind=GameEventKind.DETECTION_FAILED,
                    turn_index=at.turn_index,
                    player_index=at.player_index,
                    accepted=False,
                    camera_armed=True,
                    client_id=client_id,
                    failure=failure.value,
                    metrics=metrics,
                ),
            )
    except Exception:  # noqa: BLE001 - diagnostics must not break the game
        logger.exception("[evaluation] could not record %s", failure)


def remember_frame(game_id: str, jpeg: bytes) -> None:
    """Keep the empty board a camera just calibrated on: it is the base image of
    the next visit's throw series."""
    frames.remember(game_id, jpeg)


def note_throw(game_id: str, jpeg: bytes) -> None:
    """Add a located throw to the open visit's frames."""
    frames.add_throw(game_id, jpeg)


def settle_visit(game: Game) -> None:
    """Close the visit that just ended, keeping its frames if the game is a test run."""
    # The handover has already opened the next visit, so the one that ended is
    # the slot before it.
    ended = len(game.turns) - 2
    if game.evaluation_enabled:
        frames.flush(game.id, ended)
    else:
        frames.discard(game.id)
