from pydantic import EmailStr, Field, field_validator

from app.api.core.dto.base import CamelModel


class RegisterDto(CamelModel):
    """The constraints are the validation: a handle with a space or a password
    under eight characters is a 422 from the schema, not a hand-written check."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("displayName must not be blank")
        return name
