from pydantic import Field

from app.api.core.dto.base import CamelModel


class IdentityConfirmationDto(CamelModel):
    """Proof for a sensitive change: the current password, or a fresh Google sign-in."""

    current_password: str | None = Field(default=None, max_length=128)
    google_credential: str | None = Field(default=None, max_length=4096)
