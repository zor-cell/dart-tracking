from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.around_the_clock import ClockOptions, ClockProgress, ClockZone
from app.api.features.game.domain.game import Game


class ClockOptionsDto(CamelModel):
    zone: ClockZone = ClockZone.ANY
    skip: bool = False

    def to_entity(self) -> ClockOptions:
        return ClockOptions(zone=self.zone, skip=self.skip)


class ClockPlayerDto(CamelModel):
    # The number to hit next, 25 for the bull; None once through.
    target: int | None
    # Targets already passed.
    done: int
    hits: int
    darts: int
    # Targets the last closed visit moved on; None before it.
    last_visit: int | None


class ClockStateDto(ClockOptionsDto):
    # One per player, in seat order.
    players: list[ClockPlayerDto]

    @classmethod
    def from_entity(cls, game: Game, options: ClockOptions, progress: ClockProgress) -> Self:
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
        return cls(zone=options.zone, skip=options.skip, players=players)
