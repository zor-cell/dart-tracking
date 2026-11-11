"""Cricket: close 20 down to 15 and the bull with three marks each; marks beyond that
score the number for as long as an opponent still has it open."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.turn import Turn

CRICKET_TARGETS = (20, 19, 18, 17, 16, 15, 25)
MARKS_TO_CLOSE = 3


class CricketScoring(StrEnum):
    """STANDARD: points go to the thrower, most points wins. CUT_THROAT: points go to
    every opponent still open, fewest wins. NO_SCORE: first to close everything wins."""

    STANDARD = "standard"
    CUT_THROAT = "cut_throat"
    NO_SCORE = "no_score"


@dataclass(frozen=True)
class CricketOptions:
    scoring: CricketScoring = CricketScoring.STANDARD


@dataclass
class CricketPlayer:
    marks: dict[int, int] = field(default_factory=lambda: dict.fromkeys(CRICKET_TARGETS, 0))
    points: int = 0
    # Marks that closed a target or scored, the base of marks per round.
    counted_marks: int = 0
    darts: int = 0

    @property
    def all_closed(self) -> bool:
        return all(marks >= MARKS_TO_CLOSE for marks in self.marks.values())


@dataclass
class CricketProgress:
    players: dict[int, CricketPlayer]
    # Counted marks of each replayed turn, in turn order.
    turn_marks: list[int] = field(default_factory=list)
    winner_id: int | None = None


def cricket_progress(
    player_ids: Sequence[int], turns: Sequence[Turn], options: CricketOptions
) -> CricketProgress:
    """Replay the darts in throwing order; the first dart that meets the win stops it."""
    progress = CricketProgress({player_id: CricketPlayer() for player_id in player_ids})
    for turn in turns:
        marks = 0
        for dart in turn.darts:
            if progress.winner_id is not None:
                break
            marks += _throw(progress.players, turn.player_id, dart, options.scoring)
            progress.winner_id = _winner(progress.players, turn.player_id, options.scoring)
        progress.turn_marks.append(marks)
    return progress


def _throw(
    players: dict[int, CricketPlayer], thrower_id: int, dart: Dart, scoring: CricketScoring
) -> int:
    """Book one dart and return the marks it counted."""
    thrower = players[thrower_id]
    thrower.darts += 1
    if dart.value not in thrower.marks or dart.multiplier == 0:
        return 0
    before = thrower.marks[dart.value]
    closing = min(dart.multiplier, MARKS_TO_CLOSE - before)
    extra = dart.multiplier - closing
    thrower.marks[dart.value] = before + closing

    open_to = [
        player
        for player_id, player in players.items()
        if player_id != thrower_id and player.marks[dart.value] < MARKS_TO_CLOSE
    ]
    if scoring is CricketScoring.NO_SCORE or not open_to:
        extra = 0
    elif scoring is CricketScoring.STANDARD:
        thrower.points += extra * dart.value
    else:
        for player in open_to:
            player.points += extra * dart.value

    thrower.counted_marks += closing + extra
    return closing + extra


def _winner(
    players: dict[int, CricketPlayer], thrower_id: int, scoring: CricketScoring
) -> int | None:
    """Whoever has closed everything with the best points, the thrower first on a tie."""
    order = [thrower_id, *(player_id for player_id in players if player_id != thrower_id)]
    for player_id in order:
        player = players[player_id]
        others = [other.points for other_id, other in players.items() if other_id != player_id]
        if not player.all_closed:
            continue
        if scoring is CricketScoring.NO_SCORE or not others:
            return player_id
        if scoring is CricketScoring.STANDARD and player.points >= max(others):
            return player_id
        if scoring is CricketScoring.CUT_THROAT and player.points <= min(others):
            return player_id
    return None
