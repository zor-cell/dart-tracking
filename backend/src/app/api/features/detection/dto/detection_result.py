from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.services.dart_overlay import build_overlay


class DetectionResultDto(CamelModel):
    """Server -> client: outcome of locating a dart in a throw frame, in this camera's
    image space: the dart, its score and an `overlay` of normalized polylines, or the
    stage that gave up.
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
