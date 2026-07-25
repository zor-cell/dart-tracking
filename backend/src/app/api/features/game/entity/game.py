"""Domain model and x01 rules for the game feature.

The turn list is the single source of truth: every score (remaining points,
winner, darts left) is derived from it. Nothing is stored twice, and the full
throw history stays available for the statistics planned in the roadmap.
"""

from dataclasses import dataclass, field

from app.api.features.game.entity.checkout import checkout_route
from app.api.features.game.entity.checkout_mode import CheckoutMode
from app.api.features.game.entity.game_mode import GameMode
from app.api.features.game.entity.player import Player
from app.api.features.game.entity.turn import Turn

DARTS_PER_TURN = 3


@dataclass
class Game:
    id: str
    mode: GameMode
    players: list[Player]
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    current_player_index: int = 0
    turns: list[Turn] = field(default_factory=list)

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

    def remaining(self, player_id: int) -> int:
        """Points left for a player: the starting score minus every dart of that
        player's turns, skipping busted ones."""
        scored = sum(
            sum(turn.darts)
            for turn in self.turns
            if turn.player_id == player_id and not turn.busted
        )
        return self.mode - scored

    def last_turn(self, player_id: int) -> Turn | None:
        """The player's most recent turn that has darts — the visit score to show
        next to them. Skips the empty turn opened when play returns to them, so a
        completed visit's total stays visible until they actually throw again."""
        return next(
            (turn for turn in reversed(self.turns) if turn.player_id == player_id and turn.darts),
            None,
        )

    def register_dart(self, points: int) -> None:
        """Apply one dart to the current player's open turn. Overshooting busts
        the whole turn; the double-out rule is not modelled yet.

        The visit auto-advances to the next player once it is over — three darts
        thrown or busted — so there is no separate "next player" step; a winning
        dart ends the leg instead of advancing."""
        if self.winner is not None or self.darts_remaining <= 0:
            return
        turn = self.current_turn
        turn.darts.append(points)
        if self.remaining(turn.player_id) < 0:
            turn.busted = True
        if self.darts_remaining == 0 and self.winner is None:
            self.next_player()

    def undo(self) -> None:
        """Step back one action, across turn boundaries.

        Removes the last dart of the open turn; if that turn has not started yet,
        the preceding `next_player` is undone instead, which reopens the previous
        player's turn so a further undo pops a dart from it.

        Deliberately not guarded by `winner`: correcting a misrecorded winning
        dart is exactly when undo is needed.
        """
        turn = self.current_turn
        if turn.darts:
            turn.darts.pop()
            # A bust is always caused by the turn's last dart, so removing that
            # dart necessarily clears it.
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

    def next_player(self) -> None:
        if self.winner is not None:
            return
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self._start_turn()

    def _start_turn(self) -> None:
        self.turns.append(Turn(player_id=self.current_player.id))
