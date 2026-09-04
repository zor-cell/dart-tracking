from app.api.core.dto.base import CamelModel
from app.api.features.auth.dto.user import UserDto


class SessionDto(CamelModel):
    """What a client holds after signing in. The refresh token is deliberately
    not in here — it travels in an httpOnly cookie, out of reach of scripts."""

    access_token: str
    expires_in: int
    user: UserDto
