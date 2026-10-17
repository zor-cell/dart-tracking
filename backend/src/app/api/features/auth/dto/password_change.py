from pydantic import Field

from app.api.core.dto.base import CamelModel


class PasswordChangeDto(CamelModel):
    """The new password follows the registration rules; the current one only has an upper bound."""

    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
