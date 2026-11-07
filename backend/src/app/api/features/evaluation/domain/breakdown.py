"""The judged darts split by technical properties: tracker version, camera tilt, blob
cohesion. Shared by the evaluation page and the Markdown report."""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from app.api.features.calibration.domain.camera_angle import CameraAngle
from app.api.features.evaluation.domain.accuracy import (
    Accuracy,
    JudgedGame,
    Judgement,
    summarise,
)
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.domain.visit_replay import Visit

# Upper edges of the camera tilt bands, in degrees.
TILT_BANDS = (20, 35, 50)
# Radius of the board itself, in mm. A booked MISS beyond it lies off the board.
BOARD_EDGE_MM = 225.0
UNKNOWN = "unknown"


class GroupKind(StrEnum):
    VERSION = "version"
    TILT = "tilt"
    FRAGMENTS = "fragments"


@dataclass(frozen=True)
class GroupFigures:
    """How the darts of one group were judged and why its detections came back empty.
    `key` is a code, not a label."""

    key: str
    accuracy: Accuracy
    failures: list[tuple[str, int]]


@dataclass
class _Members:
    """What one group collects while the games are sorted into groups."""

    game_ids: set[str] = field(default_factory=set)
    games: list[JudgedGame] = field(default_factory=list)
    visits: list[Visit] = field(default_factory=list)
    judgements: list[Judgement] = field(default_factory=list)


@dataclass(frozen=True)
class MissBand:
    """Booked MISS darts whose tip landed on the board or beyond its edge."""

    on_board: bool
    correct: int
    wrong: int
    phantom: int


def version_of(game: JudgedGame) -> str:
    versions = game.game.tracker_versions
    return ", ".join(map(str, versions)) if versions else UNKNOWN


def tilt_band(angle: CameraAngle) -> str:
    """Overall tilt off the board normal as `low-high`, the last band as `low+`."""
    low = 0
    for high in TILT_BANDS:
        if angle.tilt < high:
            return f"{low}-{high}"
        low = high
    return f"{low}+"


def fragments_of(judgement: Judgement) -> str | None:
    count = judgement.fragments
    if count is None:
        return None
    return "1" if count <= 1 else "2" if count == 2 else "3+"


# The group of a whole game; blob cohesion is the one kind that splits a game's darts.
_GAME_KEYS: dict[GroupKind, Callable[[JudgedGame], str | None]] = {
    GroupKind.VERSION: version_of,
    GroupKind.TILT: lambda game: None if game.camera is None else tilt_band(game.camera),
}


def _order(key: str) -> tuple[float, str]:
    """Versions, tilts and blobs ascending, the unknown last."""
    leading = key.split(",")[0].split("-")[0].rstrip("+")
    return (float(leading) if leading.isdigit() else math.inf, key)


def _members(games: list[JudgedGame], kind: GroupKind) -> dict[str, _Members]:
    """The games, visits and darts of each group; a dart split off from its game brings
    neither visits nor failures along."""
    groups: dict[str, _Members] = {}
    for game in games:
        if kind is GroupKind.FRAGMENTS:
            for judgement in game.judgements:
                key = fragments_of(judgement)
                if key is not None:
                    group = groups.setdefault(key, _Members())
                    group.game_ids.add(game.game.id)
                    group.judgements.append(judgement)
            continue
        key = _GAME_KEYS[kind](game)
        if key is not None:
            group = groups.setdefault(key, _Members())
            group.game_ids.add(game.game.id)
            group.games.append(game)
            group.visits.extend(game.visits)
            group.judgements.extend(game.judgements)
    return groups


def breakdown(games: list[JudgedGame], kind: GroupKind) -> list[GroupFigures]:
    """One row per group of `kind`, in its natural order; darts it cannot place are left out."""
    groups = _members(games, kind)
    return [
        GroupFigures(
            key=key,
            accuracy=summarise(len(group.game_ids), group.visits, group.judgements),
            failures=failures(group.games),
        )
        for key, group in sorted(groups.items(), key=lambda item: _order(item[0]))
    ]


def failures(games: list[JudgedGame]) -> list[tuple[str, int]]:
    """Why detections came back empty, most frequent first."""
    counts = Counter(event.failure for game in games for event in game.events if event.failure)
    return counts.most_common()


def booked_misses(judgements: list[Judgement]) -> list[MissBand]:
    """Booked MISS darts by where their tip landed; a correct one off the board may be
    a phantom that met a zero entered by hand."""
    booked = [
        j for j in judgements
        if j.tracked is not None and j.tracked.label == "MISS" and j.tracked.position
    ]
    counts = Counter(
        (math.hypot(*j.tracked.position) <= BOARD_EDGE_MM, j.outcome) for j in booked
    )
    return [
        MissBand(
            on_board=on_board,
            correct=counts[on_board, DartOutcome.CORRECT],
            wrong=counts[on_board, DartOutcome.WRONG],
            phantom=counts[on_board, DartOutcome.PHANTOM],
        )
        for on_board in (True, False)
    ]


def mismatches(judgements: list[Judgement]) -> list[Judgement]:
    """Every dart the tracker got wrong, nearest to its segment first."""
    wrong = [j for j in judgements if j.outcome is not DartOutcome.CORRECT]
    return sorted(wrong, key=lambda j: (j.off_by_mm is None, j.off_by_mm or 0.0))


def located(judgements: list[Judgement]) -> list[Judgement]:
    """Every booked dart the camera located a tip for, right or wrong."""
    return [j for j in judgements if j.tracked is not None and j.tracked.position]


@dataclass(frozen=True)
class Breakdowns:
    """Everything the report splits the judged darts by, beyond the totals."""

    groups: dict[GroupKind, list[GroupFigures]]
    failures: list[tuple[str, int]]
    misses: list[MissBand]
    mismatches: list[Judgement]
    tips: list[Judgement]


def breakdowns_of(games: list[JudgedGame]) -> Breakdowns:
    judgements = [j for game in games for j in game.judgements]
    return Breakdowns(
        groups={kind: breakdown(games, kind) for kind in GroupKind},
        failures=failures(games),
        misses=booked_misses(judgements),
        mismatches=mismatches(judgements),
        tips=located(judgements),
    )
