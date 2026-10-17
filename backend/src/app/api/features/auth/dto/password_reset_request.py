from pydantic import EmailStr

from app.api.core.dto.base import CamelModel


class PasswordResetRequestDto(CamelModel):
    email: EmailStr
