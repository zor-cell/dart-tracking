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
    Judgement,
)
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.domain.breakdown import (
    Breakdowns,
    GroupFigures,
    GroupKind,
)


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
    missed_zeros: int

    @classmethod
    def from_entity(cls, field: FieldErrors) -> Self:
        return cls(
            kind=field.kind,
            thrown=field.thrown,
            correct=field.correct,
            wrong=field.wrong,
            wrong_ring=field.wrong_ring,
            missed=field.missed,
            missed_zeros=field.missed_zeros,
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
    tracker_versions: list[int]
    camera: CameraAngleDto | None
    summary: AccuracySummaryDto

    @classmethod
    def from_entity(cls, judged: GameAccuracy) -> Self:
        return cls(
            game_id=judged.game.id,
            mode=judged.game.mode,
            created_at=judged.game.created_at,
            evaluation_enabled=judged.game.evaluation_enabled,
            tracker_versions=list(judged.game.tracker_versions),
            camera=CameraAngleDto.from_entity(judged.camera) if judged.camera else None,
            summary=AccuracySummaryDto.from_entity(judged.accuracy),
        )


class FailureCountDto(CamelModel):
    failure: str
    count: int

    @classmethod
    def all_of(cls, failures: list[tuple[str, int]]) -> list[Self]:
        return [cls(failure=failure, count=count) for failure, count in failures]


class GroupRowDto(CamelModel):
    """One group's darts; `key` is a code the page words, e.g. `20-35` or `3+`."""

    key: str
    summary: AccuracySummaryDto
    failures: list[FailureCountDto]

    @classmethod
    def from_entity(cls, row: GroupFigures) -> Self:
        return cls(
            key=row.key,
            summary=AccuracySummaryDto.from_entity(row.accuracy),
            failures=FailureCountDto.all_of(row.failures),
        )


class GroupBreakdownDto(CamelModel):
    kind: GroupKind
    rows: list[GroupRowDto]

    @classmethod
    def from_entity(cls, kind: GroupKind, rows: list[GroupFigures]) -> Self:
        return cls(kind=kind, rows=[GroupRowDto.from_entity(row) for row in rows])


class MismatchDto(CamelModel):
    """A dart the tracker got wrong; `offBy` in millimetres, for a located wrong one."""

    game_id: str
    turn_index: int
    position: int
    outcome: DartOutcome
    tracked: str | None
    expected: str | None
    off_by: float | None
    fragments: int | None

    @classmethod
    def from_entity(cls, judgement: Judgement) -> Self:
        return cls(
            game_id=judgement.game_id,
            turn_index=judgement.turn_index,
            position=judgement.position,
            outcome=judgement.outcome,
            tracked=judgement.tracked.label if judgement.tracked else None,
            expected=judgement.expected_label,
            off_by=_rounded(judgement.off_by_mm),
            fragments=judgement.fragments,
        )


class TipDto(CamelModel):
    """Where the camera located a booked dart, in board millimetres, the field it booked
    and how it was judged."""

    x: float
    y: float
    tracked: str
    outcome: DartOutcome

    @classmethod
    def from_entity(cls, judgement: Judgement) -> Self:
        x, y = judgement.tracked.position
        return cls(
            x=round(x, 1),
            y=round(y, 1),
            tracked=judgement.tracked.label,
            outcome=judgement.outcome,
        )


class AccuracyReportDto(CamelModel):
    """Totals plus every game on its own, so the page switches without asking
    the server again, and the splits of the report over all of them."""

    total: AccuracySummaryDto
    games: list[GameAccuracyDto]
    groups: list[GroupBreakdownDto]
    failures: list[FailureCountDto]
    mismatches: list[MismatchDto]
    tips: list[TipDto]

    @classmethod
    def from_entity(cls, overview: AccuracyOverview, breakdowns: Breakdowns) -> Self:
        return cls(
            total=AccuracySummaryDto.from_entity(overview.total),
            games=[GameAccuracyDto.from_entity(game) for game in overview.games],
            groups=[
                GroupBreakdownDto.from_entity(kind, rows)
                for kind, rows in breakdowns.groups.items()
            ],
            **_issues(breakdowns),
        )


class GameReportDto(CamelModel):
    """One game on its own, with the darts the tracker got wrong in it."""

    game: GameAccuracyDto
    failures: list[FailureCountDto]
    mismatches: list[MismatchDto]
    tips: list[TipDto]

    @classmethod
    def from_entity(cls, game: GameAccuracy, breakdowns: Breakdowns) -> Self:
        return cls(game=GameAccuracyDto.from_entity(game), **_issues(breakdowns))


def _issues(breakdowns: Breakdowns) -> dict[str, list]:
    return {
        "failures": FailureCountDto.all_of(breakdowns.failures),
        "mismatches": [MismatchDto.from_entity(j) for j in breakdowns.mismatches],
        "tips": [TipDto.from_entity(j) for j in breakdowns.tips],
    }


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
