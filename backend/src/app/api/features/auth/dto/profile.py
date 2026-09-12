from pydantic import Field, field_validator

from app.api.core.dto.base import CamelModel


class ProfileDto(CamelModel):
    """The two names an account carries, and the body of the write that changes
    them. Sent complete rather than as a patch, like the settings — a name never
    has an undefined state on the wire."""

    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)

    @field_validator("display_name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("displayName must not be blank")
        return name
