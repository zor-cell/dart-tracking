"""Who finishes in which place in a race to the goal, replayed round by round:
the rest of a round may catch up after a finish, a shared finish replays the
round between those who shared it, and play may go on for the places after."""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, Self

from app.api.features.game.domain.turn import Turn

DARTS_PER_TURN = 3


@dataclass(frozen=True)
class FinishRules:
    # Whether the players after a finish still throw their visit of the round.
    catch_up: bool = False
    # Whether play goes on for the places after the winner.
    play_on: bool = False


class RaceBoard(Protocol):
    """Where the players of a race stand; the replay copies it to undo a round."""

    def play(self, turn: Turn) -> None: ...

    def reached(self, player_id: int) -> bool: ...

    def copy(self) -> Self: ...


@dataclass
class Finish[B: RaceBoard]:
    board: B
    # The places decided so far, best first.
    places: list[int] = field(default_factory=list)
    # Who reached the goal: placed, or finished in the round under way. A tiebreak
    # takes its players' finish back, so they count again only once they repeat it.
    finishers: list[int] = field(default_factory=list)
    # Who sits out until the players ahead of them are placed.
    waiting: list[int] = field(default_factory=list)
    # Who still throws in the round under way, in seat order.
    pending: list[int] = field(default_factory=list)
    # Turns a tiebreak took back: they score nothing.
    voided: set[int] = field(default_factory=set)
    over: bool = False


def race[B: RaceBoard](
    seats: Sequence[int], turns: Sequence[Turn], rules: FinishRules, board: B
) -> Finish[B]:
    """Replay the turns in throwing order. The last one closes its round only once
    it takes no more darts; a shared finish stands until the visit is handed over."""
    replay = _Race(list(seats), rules, board)
    for index, turn in enumerate(turns):
        if replay.over:
            break
        last = index == len(turns) - 1
        replay.throw(index, turn, last)
    return replay.result()


class _Race[B: RaceBoard]:
    def __init__(self, seats: list[int], rules: FinishRules, board: B) -> None:
        self.seats = seats
        self.rules = rules
        self.board = board
        # The field at the bottom, each tiebreak above the players it is ahead of.
        self.groups: list[list[int]] = [list(seats)]
        self.places: list[int] = []
        # Placed by finishing rather than for being the last one left.
        self.reached: set[int] = set()
        self.voided: set[int] = set()
        self.over = False
        # The standing a shared finish left, shown until the last visit is handed over.
        self.held: Finish[B] | None = None
        self._new_round()

    def _new_round(self) -> None:
        self.start = self.board.copy()
        self.round: list[tuple[int, Turn]] = []
        self.pending = list(self.groups[-1])
        self.finishers: list[int] = []

    def throw(self, index: int, turn: Turn, last: bool) -> None:
        player = turn.player_id
        if player in self.pending:
            self.pending.remove(player)
        self.board.play(turn)
        self.round.append((index, turn))
        reached = self.board.reached(player)
        if reached and player not in self.finishers:
            self.finishers.append(player)
            if not self.rules.catch_up:
                self._place(player)
        closed = not last or reached or turn.busted or len(turn.darts) >= DARTS_PER_TURN
        if not self.over and not self.pending and closed:
            self._end_round(last)

    def _end_round(self, last: bool) -> None:
        if self.rules.catch_up and len(self.finishers) == 1:
            self._place(self.finishers[0])
        elif self.rules.catch_up and len(self.finishers) > 1:
            if last:
                reached = self.reached | set(self.finishers)
                finishers = [player for player in self.seats if player in reached]
                self.held = Finish(self.board, list(self.places), finishers, voided=set(self.voided))
            self._tie(self.finishers)
        if not self.over:
            self._new_round()

    def _tie(self, tied: list[int]) -> None:
        """Take back the tied players' visits of this round and let them play it again."""
        self.board = self.start
        for index, turn in self.round:
            if turn.player_id in tied:
                self.voided.add(index)
            else:
                self.board.play(turn)
        group = self.groups[-1]
        ahead = [player for player in group if player in tied]
        group[:] = [player for player in group if player not in tied]
        self.groups.append(ahead)

    def _place(self, player: int) -> None:
        """Give the player the next place; a tiebreak down to one player places it too."""
        self.places.append(player)
        self.reached.add(player)
        self.groups[-1].remove(player)
        if not self.rules.play_on:
            self.over = True
            return
        while len(self.groups) > 1 and len(self.groups[-1]) <= 1:
            last = self.groups.pop()
            self.places.extend(last)
            self.reached.update(last)
        left = [player for group in self.groups for player in group]
        if len(left) <= 1:
            self.places.extend(left)
            self.over = True

    def result(self) -> Finish[B]:
        if self.held is not None:
            return replace(self.held, pending=self.pending)
        running = set() if self.over else set(self.finishers)
        finishers = [player for player in self.seats if player in self.reached | running]
        if self.over:
            return Finish(self.board, self.places, finishers, voided=self.voided, over=True)
        sitting_out = {player for group in self.groups[:-1] for player in group}
        return Finish(
            self.board,
            self.places,
            finishers,
            waiting=[player for player in self.seats if player in sitting_out],
            pending=self.pending,
            voided=self.voided,
        )
