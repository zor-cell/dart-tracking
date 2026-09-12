from pydantic import EmailStr, Field

from app.api.features.auth.dto.profile import ProfileDto


class RegisterDto(ProfileDto):
    """The constraints are the validation: a handle with a space or a password
    under eight characters is a 422 from the schema, not a hand-written check."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
