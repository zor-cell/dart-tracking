"""The darts of a logged game whose tracked tip a correction keeps, for the darts
booked before corrections kept them."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.api.features.evaluation.domain.accuracy import judge
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.domain.game_event import GameEvent
from app.api.features.evaluation.domain.visit_replay import replay
from app.api.features.game.domain.correction import corrected
from app.api.features.game.domain.dart import Dart


@dataclass(frozen=True)
class SnappedDart:
    turn_index: int
    dart_index: int  # place in the visit, from 0
    dart: Dart  # the booked field with the tip moved into it


def snapped_darts(game_id: str, events: Iterable[GameEvent]) -> list[SnappedDart]:
    """Each mis-scored dart whose tracked tip lay close enough to its booked field."""
    found: list[SnappedDart] = []
    for visit in replay(events):
        for judgement in judge(game_id, visit) if visit.tracked else []:
            expected, tracked = judgement.expected_segment, judgement.tracked
            if judgement.outcome is not DartOutcome.WRONG or expected is None or tracked is None:
                continue
            camera = Dart(value=tracked.value or 0, multiplier=tracked.multiplier or 0, position=tracked.position)
            fixed = corrected(camera, Dart(value=expected.value, multiplier=expected.multiplier))
            if fixed.snapped:
                found.append(SnappedDart(judgement.turn_index, judgement.dart - 1, fixed))
    return found
