from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.around_the_clock import ClockProgress, ClockZone
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_variant import GameVariant


class ClockSettingsDto(CamelModel):
    variant: Literal[GameVariant.AROUND_THE_CLOCK] = GameVariant.AROUND_THE_CLOCK
    zone: ClockZone = ClockZone.ANY
    skip: bool = False
    catch_up: bool = False
    play_on: bool = False


class ClockPlayerDto(CamelModel):
    # The number to hit next, 25 for the bull; None once through.
    target: int | None
    # Targets already passed.
    done: int
    hits: int
    darts: int
    # Targets the last closed visit moved on; None before it.
    last_visit: int | None


class ClockStandingDto(CamelModel):
    variant: Literal[GameVariant.AROUND_THE_CLOCK] = GameVariant.AROUND_THE_CLOCK
    # One per player, in seat order.
    players: list[ClockPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, progress: ClockProgress) -> Self:
        players = []
        for player in game.players:
            standing = progress.players[player.id]
            last = game.last_closed_turn(player.id)
            players.append(
                ClockPlayerDto(
                    target=standing.target,
                    done=standing.position,
                    hits=standing.hits,
                    darts=standing.darts,
                    last_visit=None if last is None else progress.turn_steps[last],
                )
            )
        return cls(players=players)
