"""Domain model and x01 rules for the game feature.

The turn list is the single source of truth: every score (remaining points,
winner, darts left) is derived from it. Nothing is stored twice, and the full
throw history stays available for the statistics planned in the roadmap.
"""

from dataclasses import dataclass, field

from app.api.features.game.entity.game_mode import GameMode
from app.api.features.game.entity.player import Player
from app.api.features.game.entity.turn import Turn

DARTS_PER_TURN = 3


@dataclass
class Game:
    id: str
    mode: GameMode
    players: list[Player]
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

    def remaining(self, player_id: int) -> int:
        """Points left for a player: the starting score minus every dart of that
        player's turns, skipping busted ones."""
        scored = sum(
            sum(turn.darts)
            for turn in self.turns
            if turn.player_id == player_id and not turn.busted
        )
        return self.mode - scored

    def register_dart(self, points: int) -> None:
        """Apply one dart to the current player's open turn. Overshooting busts
        the whole turn; the double-out rule is not modelled yet."""
        if self.winner is not None or self.darts_remaining <= 0:
            return
        turn = self.current_turn
        turn.darts.append(points)
        if self.remaining(turn.player_id) < 0:
            turn.busted = True

    def next_player(self) -> None:
        if self.winner is not None:
            return
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self._start_turn()

    def _start_turn(self) -> None:
        self.turns.append(Turn(player_id=self.current_player.id))
