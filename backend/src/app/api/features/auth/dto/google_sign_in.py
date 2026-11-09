from pydantic import Field

from app.api.core.dto.base import CamelModel


class GoogleSignInDto(CamelModel):
    """The ID token the Google sign-in button handed the browser."""

    credential: str = Field(min_length=1, max_length=4096)
