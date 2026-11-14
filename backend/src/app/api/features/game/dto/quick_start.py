from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.quick_start import PlayedSetup, QuickStartSeat
from app.api.features.game.dto.game_settings import GameSettingsDto, settings_dto


class QuickStartSeatDto(CamelModel):
    # The identity to seat, or null to seat a guest by `name`.
    player_id: str | None
    name: str


class QuickStartDto(CamelModel):
    """A new game's settings in the shape the create call takes, ready to send."""

    settings: GameSettingsDto
    players: list[QuickStartSeatDto]

    @classmethod
    def from_entity(cls, played: PlayedSetup, seats: list[QuickStartSeat]) -> Self:
        return cls(
            settings=settings_dto(played.setup),
            players=[QuickStartSeatDto(player_id=seat.player_id, name=seat.name) for seat in seats],
        )
