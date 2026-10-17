from pydantic import EmailStr, Field

from app.api.core.dto.base import CamelModel


class EmailChangeDto(CamelModel):
    new_email: EmailStr
    current_password: str = Field(max_length=128)
