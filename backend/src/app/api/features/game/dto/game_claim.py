from pydantic import Field

from app.api.core.dto.base import CamelModel


class GameClaimTokenDto(CamelModel):
    game_id: str = Field(max_length=64)
    token: str = Field(max_length=128)


class ClaimableGamesQueryDto(CamelModel):
    """The anonymous games a device set up, each with the token it was handed."""

    claims: list[GameClaimTokenDto] = Field(max_length=50)


class GameClaimDto(CamelModel):
    token: str = Field(max_length=128)
    # The seat the account played on; null when it only kept score.
    seat: int | None = None
