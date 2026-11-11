from typing import Self

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.killer import (
    KillerOptions,
    KillerProgress,
    KillerZone,
    deal_numbers,
)


class KillerOptionsDto(CamelModel):
    lives: int = Field(3, ge=1, le=9)
    zone: KillerZone = KillerZone.DOUBLE

    def to_entity(self, players: int) -> KillerOptions:
        """Deals every seat its own number at random."""
        return KillerOptions(numbers=deal_numbers(players), lives=self.lives, zone=self.zone)


class KillerPlayerDto(CamelModel):
    number: int
    lives: int
    killer: bool
    # Lives this player took from others.
    kills: int


class KillerStateDto(KillerOptionsDto):
    # One per player, in seat order.
    players: list[KillerPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, options: KillerOptions, progress: KillerProgress) -> Self:
        players = []
        for player in game.players:
            standing = progress.players[player.id]
            players.append(
                KillerPlayerDto(
                    number=standing.number,
                    lives=standing.lives,
                    killer=standing.killer,
                    kills=standing.kills,
                )
            )
        return cls(lives=options.lives, zone=options.zone, players=players)
