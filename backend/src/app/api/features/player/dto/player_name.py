from pydantic import Field, field_validator

from app.api.core.dto.base import CamelModel


class PlayerNameDto(CamelModel):
    """The name of a player in the address book, for creating or renaming it."""

    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be blank")
        return name
