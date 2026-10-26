"""Domain model and scoring rules for the game feature.

The turn list is the single source of truth: every score (remaining points,
winner, darts left) is derived from it. Nothing is stored twice, and the full
throw history stays available for the statistics planned in the roadmap.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.checkout import Setup, checkout_route, setup_route
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn

DARTS_PER_TURN = 3


@dataclass
class Game:
    id: str
    mode: GameMode
    players: list[Player]
    variant: GameVariant = GameVariant.X01
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    evaluation_enabled: bool = False
    current_player_index: int = 0
    turns: list[Turn] = field(default_factory=list)
    # Darts the camera located after a win or bust closed the open visit, in
    # throwing order. They score nothing until a correction reopens the visit.
    shadow_darts: list[Dart] = field(default_factory=list)
    revision: int = 0
    # When the stored game last changed; None until it has been written once.
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        # Invariant: a turn is always open for the current player, so `turns` is
        # never empty and `current_turn` never has to guess where it ends.
        if not self.turns:
            self._start_turn()

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    @property
    def current_turn(self) -> Turn:
        return self.turns[-1]

    @property
    def darts_remaining(self) -> int:
        turn = self.current_turn
        return 0 if turn.busted else DARTS_PER_TURN - len(turn.darts)

    @property
    def winner(self) -> Player | None:
        return next((player for player in self.players if self.remaining(player.id) == 0), None)

    @property
    def can_undo(self) -> bool:
        return bool(self.current_turn.darts) or len(self.turns) > 1

    @property
    def checkout(self) -> list[str] | None:
        """A suggested finish for the current player within this turn's darts, or
        None when none exists. Depends on the checkout mode: double-out routes
        must end on a double."""
        if self.winner is not None:
            return None
        route = checkout_route(
            self.remaining(self.current_player.id),
            self.darts_remaining,
            self.checkout_mode is CheckoutMode.DOUBLE_OUT,
            self.current_player.preferred_doubles,
        )
        return list(route) if route is not None else None

    @property
    def setup(self) -> Setup | None:
        """What to throw with the last dart when this visit cannot finish, so the
        next one can. x01 only: in elimination the reset route fills that gap."""
        if (
            self.variant is not GameVariant.X01
            or self.winner is not None
            or self.darts_remaining != 1
        ):
            return None
        return setup_route(
            self.remaining(self.current_player.id),
            1,
            self.checkout_mode is CheckoutMode.DOUBLE_OUT,
            self.current_player.preferred_doubles,
        )

    @property
    def elimination(self) -> list[str] | None:
        """A route that lands exactly on an opponent's score, resetting them, or
        None when none fits the darts left. The easiest target wins: fewest
        darts first, then the smallest gap."""
        if self.variant is not GameVariant.ELIMINATION or self.winner is not None:
            return None

        scores = self._scores()
        mine = scores[self.current_player.id]
        best: tuple[tuple[int, int], tuple[str, ...]] | None = None
        for player in self.players:
            # A gap of zero is not a target: hitting it would score nothing, and
            # the zero exemption in `_eliminate` means it resets nobody.
            gap = scores[player.id] - mine
            if player.id == self.current_player.id or gap <= 0:
                continue
            # No double needed: a reset is not a finish, so any field will do.
            route = checkout_route(gap, self.darts_remaining, False)
            if route is None:
                continue
            cost = (len(route), gap)
            if best is None or cost < best[0]:
                best = (cost, route)

        return list(best[1]) if best is not None else None

    def remaining(self, player_id: int) -> int:
        """Points a player still needs to finish: x01 counts this down to zero,
        elimination counts the score up to the mode. Holding the distance rather
        than the score is what lets both share the bust, win and checkout rules."""
        return self.mode - self._scores()[player_id]

    def standings_after_turns(self) -> list[dict[int, int]]:
        """Points every player still needed after each turn, in turn order."""
        return [
            {player_id: self.mode - score for player_id, score in scores.items()}
            for _, scores in self._replay()
        ]

    def _scores(self) -> dict[int, int]:
        scores = {player.id: 0 for player in self.players}
        for _, scores in self._replay():
            pass
        return scores

    def _replay(self) -> Iterator[tuple[Turn, dict[int, int]]]:
        """Points scored per player after each turn, replayed in throwing order. An
        elimination reset depends on what everyone stood at when the dart landed,
        so this cannot be a per-player sum."""
        scores = {player.id: 0 for player in self.players}
        for turn in self.turns:
            if not turn.busted:
                for dart in turn.darts:
                    scores[turn.player_id] += dart.points
                    if self.variant is GameVariant.ELIMINATION:
                        self._eliminate(scores, turn.player_id)
            yield turn, scores

    def _eliminate(self, scores: dict[int, int], thrower_id: int) -> None:
        """Reset every other player the thrower just drew level with. Zero is
        exempt: everyone starts there, so an opening miss would wipe the field."""
        hit = scores[thrower_id]
        if hit == 0:
            return
        for player in self.players:
            if player.id != thrower_id and scores[player.id] == hit:
                scores[player.id] = 0

    def register_dart(self, dart: Dart) -> bool:
        """Book a tracked dart into the open visit; whether it was booked. After a
        win or bust it is kept as a shadow dart instead, and past the third
        physical dart it is dropped."""
        if self.winner is None and self.darts_remaining > 0:
            turn = self.current_turn
            turn.darts.append(dart)
            if self._busts(dart):
                turn.busted = True
            self.revision += 1
            return True
        if len(self.current_turn.darts) + len(self.shadow_darts) < DARTS_PER_TURN:
            self.shadow_darts.append(dart)
            self.revision += 1
        return False

    def add_dart(self, dart: Dart) -> None:
        """Book a manually entered dart into any visit with room left. A won or
        busted visit is closed by its last dart, so the new one goes before it."""
        turn = self.current_turn
        darts = list(turn.darts)
        if len(darts) >= DARTS_PER_TURN:
            return
        closed = turn.busted or self.winner is not None
        darts.insert(len(darts) - 1 if closed else len(darts), dart)
        self._rescore(darts)

    def _busts(self, dart: Dart) -> bool:
        """Whether the dart just thrown spoils the visit, scoring it as nothing.

        Overshooting always does. Under double-out two more cases do: reaching
        zero with anything but a double — the bullseye is the double bull, so it
        finishes — and leaving exactly one point, which no double can finish.
        """
        remaining = self.remaining(self.current_turn.player_id)
        if remaining < 0:
            return True
        if self.checkout_mode is not CheckoutMode.DOUBLE_OUT:
            return False
        if remaining == 0:
            return dart.multiplier != 2
        return remaining == 1

    def undo(self) -> None:
        """Take back the last dart of the open turn, or, when it has none yet,
        reopen the previous turn with its darts intact. Not guarded by `winner`:
        correcting a misrecorded winning dart is exactly when undo is needed."""
        if not self.can_undo:
            return

        turn = self.current_turn
        if turn.darts:
            # The bust can sit on an earlier dart once one was inserted or moved.
            self._rescore(turn.darts[:-1])
            return
        self.revision += 1
        self.turns.pop()
        self.current_player_index = next(
            index
            for index, player in enumerate(self.players)
            if player.id == self.current_turn.player_id
        )

    def remove_dart(self, index: int) -> None:
        """Take one dart out of the open visit — what a phantom booking is
        cleared with, from any position rather than only the last."""
        turn = self.current_turn
        if not 0 <= index < len(turn.darts):
            return
        self._rescore(turn.darts[:index] + turn.darts[index + 1 :])

    def replace_dart(self, index: int, dart: Dart) -> None:
        """Book a different field for one dart of the open visit, in its place.
        Open to a full or busted visit, unlike `register_dart`: correcting the
        dart that caused the bust is the point."""
        turn = self.current_turn
        if not 0 <= index < len(turn.darts):
            return
        self._rescore(turn.darts[:index] + [dart] + turn.darts[index + 1 :])

    def move_dart(self, index: int, to_index: int) -> None:
        """Move one dart of the open visit to another place in it, for a throw
        the camera missed: entered afterwards, it lands last and belongs
        wherever it was actually thrown."""
        turn = self.current_turn
        count = len(turn.darts)
        if not (0 <= index < count and 0 <= to_index < count) or index == to_index:
            return
        darts = list(turn.darts)
        darts.insert(to_index, darts.pop(index))
        self._rescore(darts)

    def _rescore(self, darts: list[Dart]) -> None:
        """Take the open visit as this sequence of darts, re-applying the bust
        rule from the start — whether a dart busts depends on the darts before
        it, so any change to the order or the fields re-decides it."""
        turn = self.current_turn
        turn.darts = []
        turn.busted = False
        for dart in darts:
            turn.darts.append(dart)
            if self._busts(dart):
                turn.busted = True
        self._book_shadow_darts()
        self.revision += 1

    def _book_shadow_darts(self) -> None:
        """Book the shadow darts in throwing order for as long as the visit stays open."""
        turn = self.current_turn
        del self.shadow_darts[max(DARTS_PER_TURN - len(turn.darts), 0) :]
        while self.shadow_darts and self.winner is None and self.darts_remaining > 0:
            dart = self.shadow_darts.pop(0)
            turn.darts.append(dart)
            if self._busts(dart):
                turn.busted = True

    def next_player(self) -> int:
        """Hand over to the next player, booking the darts the visit still lacks as
        misses; returns how many. A visit nobody has thrown in cannot be ended, so
        a second ask for the same handover finds the fresh turn and does nothing."""
        if self.winner is not None or not self.current_turn.darts:
            return 0
        filled = 0
        while self.darts_remaining > 0:
            self.register_dart(Dart(value=0, multiplier=0))
            filled += 1
        self.revision += 1
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.shadow_darts = []
        self._start_turn()
        return filled

    def set_evaluation(self, enabled: bool) -> None:
        """Turn the test run on or off. Bumps the revision so the room is told,
        the switch being shown on every device."""
        if self.evaluation_enabled == enabled:
            return
        self.evaluation_enabled = enabled
        self.revision += 1

    def _start_turn(self) -> None:
        self.turns.append(Turn(player_id=self.current_player.id))
