from typing import Literal

from app.api.core.dto.base import CamelModel


class ConnectionEstablishedDto(CamelModel):
    """Server -> client: sent once right after the WebSocket handshake."""

    type: Literal["connection_established"] = "connection_established"
