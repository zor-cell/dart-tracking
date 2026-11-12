from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.around_the_clock import ClockOptions
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions
from app.api.features.game.domain.elimination import EliminationOptions
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions
from app.api.features.game.domain.quick_start import PlayedSetup, QuickStartSeat
from app.api.features.game.dto.around_the_clock import ClockOptionsDto
from app.api.features.game.dto.cricket import CricketOptionsDto
from app.api.features.game.dto.elimination import EliminationOptionsDto
from app.api.features.game.dto.killer import KillerOptionsDto


class QuickStartSeatDto(CamelModel):
    # The identity to seat, or null to seat a guest by `name`.
    player_id: str | None
    name: str


class QuickStartDto(CamelModel):
    """A new game's settings in the shape the create call takes, ready to send."""

    variant: GameVariant
    mode: GameMode | None
    checkout_mode: CheckoutMode | None
    cricket: CricketOptionsDto | None
    killer: KillerOptionsDto | None
    around_the_clock: ClockOptionsDto | None
    elimination: EliminationOptionsDto | None
    players: list[QuickStartSeatDto]

    @classmethod
    def from_entity(cls, played: PlayedSetup, seats: list[QuickStartSeat]) -> Self:
        setup = played.setup
        options = setup.options
        return cls(
            variant=setup.variant,
            mode=setup.mode,
            checkout_mode=setup.checkout_mode,
            cricket=(
                CricketOptionsDto(scoring=options.scoring)
                if isinstance(options, CricketOptions)
                else None
            ),
            killer=(
                KillerOptionsDto(lives=options.lives, zone=options.zone)
                if isinstance(options, KillerOptions)
                else None
            ),
            around_the_clock=(
                ClockOptionsDto(zone=options.zone, skip=options.skip)
                if isinstance(options, ClockOptions)
                else None
            ),
            elimination=(
                EliminationOptionsDto(kill=options.kill)
                if isinstance(options, EliminationOptions)
                else None
            ),
            players=[QuickStartSeatDto(player_id=seat.player_id, name=seat.name) for seat in seats],
        )
