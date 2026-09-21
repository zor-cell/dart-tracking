"""Domain model and scoring rules for the game feature.

The turn list is the single source of truth: every score (remaining points,
winner, darts left) is derived from it. Nothing is stored twice, and the full
throw history stays available for the statistics planned in the roadmap.
"""

from dataclasses import dataclass, field

from app.api.features.game.domain.checkout import checkout_route
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
    revision: int = 0

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
        )
        return list(route) if route is not None else None

    @property
    def elimination(self) -> list[str] | None:
        """A route that lands exactly on an opponent's score, resetting them, or
        None when none fits the darts left. The easiest target wins: fewest
        darts first, then the smallest gap (docs/feature/spielmodi.md §3)."""
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

    def _scores(self) -> dict[int, int]:
        """Points scored per player, replayed in throwing order. An elimination
        reset depends on what everyone stood at when the dart landed, so this
        cannot be a per-player sum (docs/feature/spielmodi.md §2)."""
        scores = {player.id: 0 for player in self.players}
        for turn in self.turns:
            if turn.busted:
                continue
            for dart in turn.darts:
                scores[turn.player_id] += dart.points
                if self.variant is GameVariant.ELIMINATION:
                    self._eliminate(scores, turn.player_id)
        return scores

    def _eliminate(self, scores: dict[int, int], thrower_id: int) -> None:
        """Reset every other player the thrower just drew level with. Zero is
        exempt: everyone starts there, so an opening miss would wipe the field."""
        hit = scores[thrower_id]
        if hit == 0:
            return
        for player in self.players:
            if player.id != thrower_id and scores[player.id] == hit:
                scores[player.id] = 0

    def register_dart(self, dart: Dart) -> None:
        """Apply one dart to the current player's open turn, busting it when the
        dart breaks the checkout rule (see `_busts`).

        Advancing to the next player is a separate, explicit step (`next_player`)
        driven by the client, so the two input modes can differ: manual entry
        advances on its own once the visit is full, while camera tracking waits
        for a confirm tap — otherwise a player walking up to pull their darts
        would be tracked as the next player's visit. A dart beyond the third (or
        after a bust) is ignored until the advance happens, which also absorbs an
        over-eager camera trigger."""
        if self.winner is not None or self.darts_remaining <= 0:
            return
        turn = self.current_turn
        turn.darts.append(dart)
        if self._busts(dart):
            turn.busted = True
        self.revision += 1

    def add_dart(self, dart: Dart) -> None:
        """Book a manually entered dart into any visit with room left, busted or
        won. After a win it goes before the finishing dart, which must stay last."""
        darts = list(self.current_turn.darts)
        if len(darts) >= DARTS_PER_TURN:
            return
        darts.insert(len(darts) - 1 if self.winner is not None else len(darts), dart)
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
        """Take back the last dart thrown, across turn boundaries.

        When the open turn has no darts yet, the preceding `next_player` is
        undone as part of the same step and the previous turn's last dart is
        removed too — an empty turn holds nothing to take back, so stopping there
        would cost a second undo to change anything.

        Deliberately not guarded by `winner`: correcting a misrecorded winning
        dart is exactly when undo is needed.
        """
        # `can_undo` is exactly the condition under which the loop below changes
        # something, so the revision can be bumped up front.
        if not self.can_undo:
            return
        self.revision += 1

        while True:
            turn = self.current_turn
            if turn.darts:
                turn.darts.pop()
                # A bust is always caused by the turn's last dart, so removing
                # that dart necessarily clears it.
                turn.busted = False
                return
            if len(self.turns) == 1:
                return
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
        dart that caused the bust is the point (docs/feature/done/korrektur.md §5)."""
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
        self.revision += 1

    def next_player(self) -> None:
        """Hand over to the next player, ending the current visit.

        A visit nobody has thrown in cannot be ended, which is what makes this
        safe to receive twice: every device in the room decides for itself
        whether a finished visit should advance (see the client's confirm
        setting), so two of them can ask at once — the second ask then finds the
        fresh, empty turn and does nothing, rather than skipping a player.
        """
        if self.winner is not None or not self.current_turn.darts:
            return
        self.revision += 1
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self._start_turn()

    def set_evaluation(self, enabled: bool) -> None:
        """Turn the test run on or off. Bumps the revision so the room is told,
        the switch being shown on every device."""
        if self.evaluation_enabled == enabled:
            return
        self.evaluation_enabled = enabled
        self.revision += 1

    def _start_turn(self) -> None:
        self.turns.append(Turn(player_id=self.current_player.id))
