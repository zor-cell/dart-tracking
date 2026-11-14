from typing import Literal, Self

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerProgress, KillerZone


class KillerSettingsDto(CamelModel):
    variant: Literal[GameVariant.KILLER] = GameVariant.KILLER
    lives: int = Field(3, ge=1, le=9)
    zone: KillerZone = KillerZone.DOUBLE


class KillerPlayerDto(CamelModel):
    number: int
    lives: int
    killer: bool
    # Lives this player took from others.
    kills: int


class KillerStandingDto(CamelModel):
    variant: Literal[GameVariant.KILLER] = GameVariant.KILLER
    # One per player, in seat order.
    players: list[KillerPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, progress: KillerProgress) -> Self:
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
        return cls(players=players)
