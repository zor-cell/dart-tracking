"""Kills in Elimination and Killer: whom a player sent back or took lives from."""

from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.game import Game
from app.api.features.game.domain.killer import KillerOptions, KillerProgress


@dataclass(frozen=True)
class GameKills:
    game_id: str
    played_at: datetime
    # Resets in Elimination, lives taken from others in Killer.
    kills: int
    # Times sent back, or lives lost to anyone, the own darts included.
    losses: int
    won: bool
    # Darts the player threw in the game.
    darts: int = 0


def game_kills(game: Game, seat: int, played_at: datetime) -> GameKills:
    """The kills of the player at `seat`, replayed from the game."""
    winner = game.winner
    won = winner is not None and winner.id == seat
    darts = sum(len(turn.darts) for turn in game.turns if turn.player_id == seat)
    progress = game.progress
    if isinstance(progress, KillerProgress) and isinstance(game.options, KillerOptions):
        player = progress.players[seat]
        losses = game.options.lives - player.lives
        return GameKills(game.id, played_at, player.kills, losses, won, darts)
    kills = game.eliminations()[seat]
    return GameKills(game.id, played_at, kills, game.times_reset()[seat], won, darts)


@dataclass
class KillStatistics:
    # Oldest first.
    games: list[GameKills] = field(default_factory=list)

    @property
    def kills(self) -> int:
        return sum(game.kills for game in self.games)

    @property
    def losses(self) -> int:
        return sum(game.losses for game in self.games)

    @property
    def darts(self) -> int:
        return sum(game.darts for game in self.games)

    @property
    def wins(self) -> int:
        return sum(game.won for game in self.games)

    @property
    def most(self) -> GameKills | None:
        """The game with the most kills, the oldest on a tie; None without a kill."""
        best = max(self.games, key=lambda game: game.kills, default=None)
        return None if best is None or best.kills == 0 else best
