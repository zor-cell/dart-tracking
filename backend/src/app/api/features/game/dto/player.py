from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.entity.player import Player
from app.api.features.game.entity.turn import Turn


class PlayerDto(CamelModel):
    id: int
    name: str
    remaining: int
    # Points thrown in the player's most recent visit (None before their first),
    # shown next to them so the auto-advance is easy to verify. `busted` marks a
    # visit that overshot and therefore scored nothing.
    last_turn: int | None
    last_turn_busted: bool

    @classmethod
    def from_entity(cls, player: Player, remaining: int, last_turn: Turn | None) -> Self:
        """`remaining` and `last_turn` are passed in because they are properties of
        the game, not of the player alone."""
        return cls(
            id=player.id,
            name=player.name,
            remaining=remaining,
            last_turn=sum(last_turn.darts) if last_turn is not None else None,
            last_turn_busted=last_turn.busted if last_turn is not None else False,
        )
