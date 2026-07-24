from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.detection.entity.dart import Dart
from app.api.features.detection.entity.detection_failure import DetectionFailure


class DartDetectedMessage(CamelModel):
    """Server -> client: outcome of locating a dart in a throw frame.

    Mirrors `CalibrationResultMessage`: on success it carries where the dart
    landed and what it scored so the client can show it (and, later, draw an
    overlay); on failure it names the stage that gave up so the client can
    advise what to change instead of only reporting that nothing was found.

    The authoritative score still arrives separately as `game_state` — this
    message is the per-throw feedback, not the source of truth for the tally.
    """

    type: Literal["dart_detected"] = "dart_detected"
    success: bool
    segment: str | None = None  # called-out form, e.g. "T20", "BULL", "MISS"
    points: int | None = None
    value: int | None = None  # sector value, 25 for the bull, 0 for a miss
    multiplier: int | None = None  # 0 miss, 1 single, 2 double, 3 triple
    tip_board: list[float] | None = None  # [x, y] in board millimetres
    failure: DetectionFailure | None = None

    @classmethod
    def detected(cls, dart: Dart) -> Self:
        return cls(
            success=True,
            segment=dart.segment.label,
            points=dart.points,
            value=dart.segment.value,
            multiplier=dart.segment.multiplier,
            tip_board=[dart.tip_board[0], dart.tip_board[1]],
        )

    @classmethod
    def failed(cls, failure: DetectionFailure) -> Self:
        return cls(success=False, failure=failure)
