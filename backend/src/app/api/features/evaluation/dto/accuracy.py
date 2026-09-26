from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.calibration.domain.camera_angle import CameraAngle
from app.api.features.evaluation.domain.accuracy import (
    Accuracy,
    AccuracyOverview,
    FieldErrors,
    FieldKind,
    GameAccuracy,
)
from app.api.features.evaluation.domain.alignment import DartOutcome


class DistanceBandDto(CamelModel):
    label: str
    darts: int


class FieldErrorsDto(CamelModel):
    kind: FieldKind
    thrown: int
    correct: int
    wrong: int
    wrong_ring: int
    missed: int

    @classmethod
    def from_entity(cls, field: FieldErrors) -> Self:
        return cls(
            kind=field.kind,
            thrown=field.thrown,
            correct=field.correct,
            wrong=field.wrong,
            wrong_ring=field.wrong_ring,
            missed=field.missed,
        )


class AccuracySummaryDto(CamelModel):
    games: int
    visits: int
    clean_visits: int
    darts_thrown: int
    darts_booked: int
    correct: int
    wrong: int
    missed: int
    missed_zeros: int
    phantom: int
    # Off-by distances in millimetres, over the mis-scored darts that carried a
    # located tip.
    bands: list[DistanceBandDto]
    mean_off_by: float | None
    median_off_by: float | None
    worst_off_by: float | None
    fields: list[FieldErrorsDto]

    @classmethod
    def from_entity(cls, accuracy: Accuracy) -> Self:
        return cls(
            games=accuracy.games,
            visits=accuracy.visits,
            clean_visits=accuracy.clean_visits,
            darts_thrown=accuracy.darts_thrown,
            darts_booked=accuracy.darts_booked,
            correct=accuracy.outcomes[DartOutcome.CORRECT],
            wrong=accuracy.outcomes[DartOutcome.WRONG],
            missed=accuracy.outcomes[DartOutcome.MISSED],
            missed_zeros=accuracy.missed_zeros,
            phantom=accuracy.outcomes[DartOutcome.PHANTOM],
            bands=[
                DistanceBandDto(label=band.label, darts=band.darts)
                for band in accuracy.bands
            ],
            mean_off_by=_rounded(accuracy.mean_off_by),
            median_off_by=_rounded(accuracy.median_off_by),
            worst_off_by=_rounded(accuracy.worst_off_by),
            fields=[FieldErrorsDto.from_entity(field) for field in accuracy.fields],
        )


class CameraAngleDto(CamelModel):
    """Viewing angles in degrees; see `CameraAngle` for the signs."""

    tilt: float
    horizontal: float
    vertical: float

    @classmethod
    def from_entity(cls, angle: CameraAngle) -> Self:
        return cls(
            tilt=round(angle.tilt, 1),
            horizontal=round(angle.horizontal, 1),
            vertical=round(angle.vertical, 1),
        )


class GameAccuracyDto(CamelModel):
    game_id: str
    mode: int
    created_at: datetime
    evaluation_enabled: bool
    tracker_version: int | None
    camera: CameraAngleDto | None
    summary: AccuracySummaryDto

    @classmethod
    def from_entity(cls, judged: GameAccuracy) -> Self:
        return cls(
            game_id=judged.game.id,
            mode=judged.game.mode,
            created_at=judged.game.created_at,
            evaluation_enabled=judged.game.evaluation_enabled,
            tracker_version=judged.game.tracker_version,
            camera=CameraAngleDto.from_entity(judged.camera) if judged.camera else None,
            summary=AccuracySummaryDto.from_entity(judged.accuracy),
        )


class AccuracyReportDto(CamelModel):
    """Totals plus every game on its own, so the page switches without asking
    the server again."""

    total: AccuracySummaryDto
    games: list[GameAccuracyDto]

    @classmethod
    def from_entity(cls, overview: AccuracyOverview) -> Self:
        return cls(
            total=AccuracySummaryDto.from_entity(overview.total),
            games=[GameAccuracyDto.from_entity(game) for game in overview.games],
        )


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
