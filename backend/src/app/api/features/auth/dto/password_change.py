from pydantic import Field

from app.api.features.auth.dto.identity_confirmation import IdentityConfirmationDto


class PasswordChangeDto(IdentityConfirmationDto):
    """The new password follows the registration rules. An account without one sets it here."""

    new_password: str = Field(min_length=8, max_length=128)
