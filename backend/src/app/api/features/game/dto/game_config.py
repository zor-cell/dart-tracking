from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_options import GameOptions
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.dto.around_the_clock import ClockOptionsDto
from app.api.features.game.dto.cricket import CricketOptionsDto
from app.api.features.game.dto.elimination import EliminationOptionsDto
from app.api.features.game.dto.killer import KillerOptionsDto
from app.api.features.game.dto.player_slot import PlayerSlotDto


class GameConfigDto(CamelModel):
    # Required for the points variants, ignored by the others.
    mode: GameMode | None = None
    players: list[PlayerSlotDto]
    variant: GameVariant = GameVariant.X01
    # Null takes double out; ignored outside the points variants.
    checkout_mode: CheckoutMode | None = CheckoutMode.DOUBLE_OUT
    # The played variant's settings; left out, its defaults.
    cricket: CricketOptionsDto | None = None
    killer: KillerOptionsDto | None = None
    around_the_clock: ClockOptionsDto | None = None
    elimination: EliminationOptionsDto | None = None
    # How a race ends; ignored outside the race variants.
    catch_up: bool = False
    play_on: bool = False
    evaluation_enabled: bool = False
    rematch_of: str | None = None

    def finish(self) -> FinishRules:
        return FinishRules(catch_up=self.catch_up, play_on=self.play_on)

    def options(self) -> GameOptions | None:
        """The domain settings of the chosen variant, Killer's numbers dealt."""
        match self.variant:
            case GameVariant.CRICKET:
                return (self.cricket or CricketOptionsDto()).to_entity()
            case GameVariant.KILLER:
                return (self.killer or KillerOptionsDto()).to_entity(len(self.players))
            case GameVariant.AROUND_THE_CLOCK:
                return (self.around_the_clock or ClockOptionsDto()).to_entity()
            case GameVariant.ELIMINATION:
                return (self.elimination or EliminationOptionsDto()).to_entity()
        return None
