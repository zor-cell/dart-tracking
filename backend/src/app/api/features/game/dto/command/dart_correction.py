from pydantic import Field

from app.api.features.game.domain.game import Game
from app.api.features.game.dto.command.game_command_base import GameCommandBase


class DartCorrectionBase(GameCommandBase):
    """Client -> server: what a command changing a booked dart carries besides its own fields."""

    # The visit corrected, from 0; None for the open one.
    turn: int | None = Field(default=None, ge=0)
    # Whether the consequence the server reported for this correction was accepted.
    confirmed: bool = False

    def is_current(self, game: Game) -> bool:
        """A closed visit stays where it is while the open one moves on."""
        if self.turn is not None and self.turn < len(game.turns) - 1:
            return True
        return super().is_current(game)
