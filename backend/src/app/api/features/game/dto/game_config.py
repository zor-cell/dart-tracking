from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_options import GameOptions
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.dto.around_the_clock import ClockOptionsDto
from app.api.features.game.dto.cricket import CricketOptionsDto
from app.api.features.game.dto.killer import KillerOptionsDto
from app.api.features.game.dto.player_slot import PlayerSlotDto


class GameConfigDto(CamelModel):
    # Required for the points variants, ignored by the others.
    mode: GameMode | None = None
    players: list[PlayerSlotDto]
    variant: GameVariant = GameVariant.X01
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    # The played variant's settings; left out, its defaults.
    cricket: CricketOptionsDto | None = None
    killer: KillerOptionsDto | None = None
    around_the_clock: ClockOptionsDto | None = None
    evaluation_enabled: bool = False
    rematch_of: str | None = None

    def options(self) -> GameOptions | None:
        """The domain settings of the chosen variant, Killer's numbers dealt."""
        match self.variant:
            case GameVariant.CRICKET:
                return (self.cricket or CricketOptionsDto()).to_entity()
            case GameVariant.KILLER:
                return (self.killer or KillerOptionsDto()).to_entity(len(self.players))
            case GameVariant.AROUND_THE_CLOCK:
                return (self.around_the_clock or ClockOptionsDto()).to_entity()
        return None
