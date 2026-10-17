from pydantic import Field

from app.api.core.dto.base import CamelModel


class PasswordResetDto(CamelModel):
    """A new password, chosen under the same rules as at registration."""

    token: str = Field(max_length=128)
    password: str = Field(min_length=8, max_length=128)
