from app.api.core.dto.base import CamelModel


class CreateGameDto(CamelModel):
    mode: int
    player_names: list[str]