from pydantic import Field

from app.api.core.dto.base import CamelModel


class LoginDto(CamelModel):
    """`identifier` is the email or the username. The password only has an upper
    bound: a too-short one is a wrong password (401), not a schema error."""

    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(max_length=128)
