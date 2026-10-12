"""What the event log says about the tracker: one judged dart per aligned
throw, and the totals over a set of them."""

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.api.features.calibration.domain.board_geometry import (
    MISS,
    Segment,
    distance_to_segment,
    segment_from_label,
)
from app.api.features.evaluation.domain.alignment import (
    DartOutcome,
    align,
    outcome_of,
)
from app.api.features.calibration.domain.camera_angle import CameraAngle
from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.evaluation.domain.visit_replay import Visit

# Upper bound of each band, in millimetres from the expected segment.
DISTANCE_BUCKETS: tuple[tuple[str, float], ...] = (
    ("<= 5 mm", 5.0),
    ("5 - 20 mm", 20.0),
    ("20 - 50 mm", 50.0),
    ("> 50 mm", float("inf")),
)


@dataclass(frozen=True)
class Judgement:
    """One aligned dart: what the camera said, and what it should have said."""

    game_id: str
    turn_index: int
    position: int  # place within the visit, 1-based
    outcome: DartOutcome
    tracked: GameEvent | None
    expected_label: str | None

    @property
    def key(self) -> str:
        return f"{self.game_id[:8]}/throw{self.turn_index}/dart{self.position}"

    @property
    def expected_segment(self) -> Segment | None:
        if self.expected_label is None:
            return None
        return segment_from_label(self.expected_label)

    @property
    def off_by_mm(self) -> float | None:
        """How far the scored tip landed from the segment it belonged in. Only
        for a booked and located dart: a missed one has no tip."""
        segment = self.expected_segment
        if self.outcome is not DartOutcome.WRONG or self.tracked is None:
            return None
        if self.tracked.position is None or segment is None:
            return None
        return distance_to_segment(*self.tracked.position, segment)

    @property
    def fragments(self) -> int | None:
        metrics = (self.tracked.metrics or {}) if self.tracked else {}
        count = metrics.get("fragment_count")
        return None if count is None else int(count)


class FieldKind(StrEnum):
    """Which kind of field a dart belonged in. The bull sorts by its multiplier:
    the 25 as a single, the bullseye as a double."""

    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    OUTSIDE = "outside"


def field_kind(segment: Segment) -> FieldKind:
    if segment.multiplier == 0:
        return FieldKind.OUTSIDE
    return (FieldKind.SINGLE, FieldKind.DOUBLE, FieldKind.TRIPLE)[segment.multiplier - 1]


@dataclass(frozen=True)
class FieldErrors:
    """How the thrown darts that belonged in one kind of field were judged."""

    kind: FieldKind
    correct: int
    wrong: int
    wrong_ring: int  # booked in the right sector, but in another ring
    missed: int

    @property
    def thrown(self) -> int:
        return self.correct + self.wrong + self.missed


@dataclass(frozen=True)
class DistanceBand:
    """How many mis-scored darts landed within one band of the buckets."""

    label: str
    darts: int


@dataclass(frozen=True)
class Accuracy:
    """The totals over a set of judged darts, plus the visits they came from."""

    games: int
    visits: int
    clean_visits: int  # accepted without a correction
    outcomes: dict[DartOutcome, int]
    missed_zeros: int  # missed darts the players booked as a zero
    # Off-by distances of the mis-scored darts that carried a located tip.
    distances: tuple[float, ...]
    fields: tuple[FieldErrors, ...] = ()

    @property
    def darts_thrown(self) -> int:
        """A phantom had no dart behind it, so it is not one that was thrown."""
        return sum(self.outcomes.values()) - self.outcomes[DartOutcome.PHANTOM]

    @property
    def darts_booked(self) -> int:
        return sum(self.outcomes.values()) - self.outcomes[DartOutcome.MISSED]

    @property
    def correct(self) -> int:
        return self.outcomes[DartOutcome.CORRECT]

    @property
    def accuracy(self) -> float:
        """Share of thrown darts booked in the right segment."""
        return self.correct / self.darts_thrown if self.darts_thrown else 0.0

    @property
    def clean_visit_rate(self) -> float:
        return self.clean_visits / self.visits if self.visits else 0.0

    @property
    def bands(self) -> list[DistanceBand]:
        bands = []
        low = 0.0
        for label, high in DISTANCE_BUCKETS:
            bands.append(
                DistanceBand(
                    label=label,
                    darts=sum(1 for d in self.distances if low < d <= high),
                )
            )
            low = high
        return bands

    @property
    def mean_off_by(self) -> float | None:
        return statistics.fmean(self.distances) if self.distances else None

    @property
    def median_off_by(self) -> float | None:
        return statistics.median(self.distances) if self.distances else None

    @property
    def worst_off_by(self) -> float | None:
        return max(self.distances) if self.distances else None


def judge(game_id: str, visit: Visit) -> list[Judgement]:
    """Align one visit's claimed darts against the ones the players accepted."""
    tracked = [event.label for event in visit.claimed]
    expected = [event.label for event in visit.accepted]

    return [
        Judgement(
            game_id=game_id,
            turn_index=visit.turn_index,
            position=position,
            outcome=outcome_of(
                tracked[left] if left is not None else None,
                expected[right] if right is not None else None,
            ),
            tracked=visit.claimed[left] if left is not None else None,
            expected_label=expected[right] if right is not None else None,
        )
        for position, (left, right) in enumerate(align(tracked, expected), start=1)
    ]


def summarise(games: int, visits: list[Visit], judgements: list[Judgement]) -> Accuracy:
    counts = Counter(judgement.outcome for judgement in judgements)
    return Accuracy(
        games=games,
        visits=len(visits),
        clean_visits=sum(1 for visit in visits if not visit.corrected),
        outcomes={outcome: counts[outcome] for outcome in DartOutcome},
        missed_zeros=sum(
            1
            for judgement in judgements
            if judgement.outcome is DartOutcome.MISSED
            and judgement.expected_segment == MISS
        ),
        distances=tuple(
            judgement.off_by_mm
            for judgement in judgements
            if judgement.off_by_mm is not None
        ),
        fields=field_errors(judgements),
    )


def field_errors(judgements: list[Judgement]) -> tuple[FieldErrors, ...]:
    """Thrown darts split by the kind of field they belonged in, every kind listed."""
    counts: dict[FieldKind, Counter[str]] = {kind: Counter() for kind in FieldKind}
    for judgement in judgements:
        expected = judgement.expected_segment
        if expected is None:
            continue
        tally = counts[field_kind(expected)]
        tally[judgement.outcome.value] += 1
        if judgement.outcome is DartOutcome.WRONG and judgement.tracked is not None:
            booked = judgement.tracked.segment
            if booked is not None and booked.value == expected.value:
                tally["wrong_ring"] += 1
    return tuple(
        FieldErrors(
            kind=kind,
            correct=tally[DartOutcome.CORRECT.value],
            wrong=tally[DartOutcome.WRONG.value],
            wrong_ring=tally["wrong_ring"],
            missed=tally[DartOutcome.MISSED.value],
        )
        for kind, tally in counts.items()
    )


@dataclass(frozen=True)
class LoggedGame:
    """A game that left an event log behind, with what it takes to name it."""

    id: str
    mode: int
    created_at: datetime
    evaluation_enabled: bool
    tracker_version: int | None = None


@dataclass(frozen=True)
class JudgedGame:
    """One game's log, its filmed visits and the darts judged in them."""

    game: LoggedGame
    events: list[GameEvent]
    visits: list[Visit]
    judgements: list[Judgement]

    @property
    def camera(self) -> CameraAngle | None:
        return camera_angle_of(self.events)


@dataclass(frozen=True)
class GameAccuracy:
    game: LoggedGame
    accuracy: Accuracy
    camera: CameraAngle | None = None


def camera_angle_of(events: list[GameEvent]) -> CameraAngle | None:
    """The scoring camera's viewing angle over a game: the median of its calibrations."""
    angles = [
        event.metrics
        for event in events
        if event.kind is GameEventKind.CALIBRATED and event.metrics
    ]
    if not angles:
        return None
    return CameraAngle(
        tilt=statistics.median(a["tilt_deg"] for a in angles),
        horizontal=statistics.median(a["horizontal_deg"] for a in angles),
        vertical=statistics.median(a["vertical_deg"] for a in angles),
        focal_px=statistics.median(a["focal_px"] for a in angles),
    )


@dataclass(frozen=True)
class AccuracyOverview:
    """Every filmed game on its own, plus the totals over all of them."""

    total: Accuracy
    games: list[GameAccuracy]
