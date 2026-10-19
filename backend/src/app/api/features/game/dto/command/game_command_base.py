from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game


class GameCommandBase(CamelModel):
    """Client -> server: what every game command carries besides its own fields."""

    # The open visit as the device saw it and the index its next dart would take;
    # None skips the check.
    turn_index: int | None = Field(default=None, ge=0)
    dart_index: int | None = Field(default=None, ge=0)

    def is_current(self, game: Game) -> bool:
        """Whether the game still holds the visit this command was made against."""
        if self.turn_index is None or self.dart_index is None:
            return True
        return (self.turn_index, self.dart_index) == (
            len(game.turns) - 1,
            len(game.current_turn.darts),
        )
