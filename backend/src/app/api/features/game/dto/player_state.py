from app.api.core.dto.base import CamelModel


class PlayerState(CamelModel):
    id: int
    name: str
    remaining: int
