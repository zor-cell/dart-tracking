from pydantic import Field

from app.api.core.dto.base import CamelModel


class AccountDeletionDto(CamelModel):
    current_password: str = Field(max_length=128)
