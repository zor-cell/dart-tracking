from pydantic import EmailStr, Field

from app.api.core.dto.base import CamelModel


class LoginDto(CamelModel):
    """Deliberately not the same constraints as `RegisterDto`: what counts as a
    valid password is a rule for choosing one. Here a too-short password is a
    wrong password (401), and only the upper bound keeps argon2 off huge input."""

    email: EmailStr
    password: str = Field(max_length=128)
