from typing import Literal

from app.api.core.dto.base import CamelModel


class AuthenticateDto(CamelModel):
    """Client -> server: the signed-in account's access token, which unlocks the
    account's messages (debug frames, the owner's `set_evaluation`) on this connection."""

    type: Literal["authenticate"]
    access_token: str
