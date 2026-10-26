"""One recorded step of a game, exactly as it happened.

Append-only: an undone dart keeps what the tracker originally claimed, which the
game's own turn list no longer holds.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.api.features.calibration.domain.board_geometry import Segment


class GameEventKind(StrEnum):
    DETECTED = "detected"  # the camera booked a dart
    SHADOW_BOOKED = "shadow_booked"  # a correction reopened the visit and booked a shadow dart
    DETECTION_FAILED = "detection_failed"  # the camera looked and found nothing
    MANUAL = "manual"  # a device booked a dart by hand
    MISS_FILLED = "miss_filled"  # a handover booked a dart the visit lacked as a miss
    UNDO = "undo"
    VISIT_REOPENED = "visit_reopened"  # an undo on an empty visit went back to the previous one
    DART_REMOVED = "dart_removed"  # a device took one dart out of the open visit
    DART_REPLACED = "dart_replaced"  # a device booked another field for one dart
    DART_MOVED = "dart_moved"  # a device moved one dart to another place in the visit
    NEXT_PLAYER = "next_player"
    CALIBRATED = "calibrated"  # the scoring camera calibrated; metrics hold its angle


@dataclass(frozen=True)
class VisitPosition:
    """Which visit was open, and whose it was, before a command was applied."""

    turn_index: int
    player_index: int
    darts: int = 0  # darts in the open visit


@dataclass(frozen=True)
class GameEvent:
    """What happened, and to which visit.

    `turn_index` is the slot of the open visit, not an id: undo can drop a visit
    and a later handover reopens that same slot for the same throws.
    """

    kind: GameEventKind
    turn_index: int
    player_index: int
    # Whether the game took the action. A dart past the third is absorbed, and
    # an undo with nothing left to take back changes nothing.
    accepted: bool
    # Whether a scoring camera was in the room. Carried by the handover that
    # opens the next visit, so a visit that never triggered is still known to
    # have been filmed.
    camera_armed: bool = False
    client_id: str | None = None
    value: int | None = None
    multiplier: int | None = None
    position: tuple[float, float] | None = None  # board millimetres
    # Position in the visit of the dart this event acts on — removed,
    # replaced, or moved, where it names where the dart came from.
    dart_index: int | None = None
    target_index: int | None = None  # where a moved dart went
    failure: str | None = None
    # Detector figures for this throw (fragment count, blob size, alignment
    # shift), so a mis-scored dart can be correlated with how it arrived.
    metrics: dict[str, float] | None = None
    tracker_version: int | None = None  # pipeline version of the server that wrote it
    created_at: datetime | None = None

    @property
    def segment(self) -> Segment | None:
        """The field this event booked, in the detection vocabulary (T20, BULL,
        MISS), or None for an event that booked nothing."""
        if self.value is None or self.multiplier is None:
            return None
        return Segment(value=self.value, multiplier=self.multiplier)

    @property
    def label(self) -> str:
        segment = self.segment
        return "" if segment is None else segment.label
