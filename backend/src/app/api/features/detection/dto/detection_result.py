from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services.dart_overlay import build_overlay


class DetectionResultDto(CamelModel):
    """Server -> client: outcome of locating a dart in a throw frame.

    Mirrors `CalibrationResultMessage`: on success it carries where the dart
    landed and what it scored, plus an `overlay` (the dart drawn back onto the
    camera picture, as normalized polylines) so the client can show it the same
    way it shows the board outline; on failure it names the stage that gave up so
    the client can advise what to change instead of only reporting that nothing
    was found.

    The authoritative score still arrives separately as `game_state` — this
    message is the per-throw feedback, not the source of truth for the tally.

    Everything here is in **this camera's image space**, and deliberately only
    that. Where the dart landed on the board travels in board millimetres on
    `DartDto.position` instead: that is camera-independent, so every device in
    the room can draw it (docs/feature/done/multi-device.md §4a). Carrying both here
    would put two coordinate systems in one message, whose numbers look alike
    and may never be mixed.
    """

    type: Literal["detection_result"] = "detection_result"
    success: bool
    segment: str | None = None  # called-out form, e.g. "T20", "BULL", "MISS"
    points: int | None = None
    overlay: list[list[list[float]]] | None = None  # dart axis + tip, normalized
    failure: DetectionFailure | None = None

    @classmethod
    def detected(cls, dart: Dart, calibration: Calibration) -> Self:
        return cls(
            success=True,
            segment=dart.segment.label,
            points=dart.points,
            overlay=build_overlay(dart, calibration),
        )

    @classmethod
    def failed(cls, failure: DetectionFailure) -> Self:
        return cls(success=False, failure=failure)
