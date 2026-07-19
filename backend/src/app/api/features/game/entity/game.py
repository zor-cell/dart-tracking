"""Domain model and x01 rules for the game feature."""

from dataclasses import dataclass, field

ALLOWED_MODES = (301, 501, 701)
DARTS_PER_TURN = 3


@dataclass
class Player:
    id: int
    name: str
    remaining: int


@dataclass
class Game:
    id: str
    mode: int
    players: list[Player]
    current_player_index: int = 0
    darts_this_turn: list[int] = field(default_factory=list)

    @property
    def winner(self) -> Player | None:
        return next((player for player in self.players if player.remaining == 0), None)

    @property
    def darts_remaining(self) -> int:
        return DARTS_PER_TURN - len(self.darts_this_turn)

    def register_dart(self, points: int) -> None:
        """Apply one dart to the current player. Overshooting is a simple bust
        (the dart is ignored); the double-out rule is not modelled yet."""
        if self.winner is not None or self.darts_remaining <= 0:
            return
        player = self.players[self.current_player_index]
        remaining = player.remaining - points
        if remaining < 0:
            return
        player.remaining = remaining
        self.darts_this_turn.append(points)

    def next_player(self) -> None:
        if self.winner is not None:
            return
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.darts_this_turn = []
