from app.api.core.dto.base import CamelModel


class PlayerDto(CamelModel):
    id: int
    name: str