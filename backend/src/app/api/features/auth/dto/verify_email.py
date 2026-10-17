from pydantic import Field

from app.api.core.dto.base import CamelModel


class VerifyEmailDto(CamelModel):
    token: str = Field(max_length=128)
