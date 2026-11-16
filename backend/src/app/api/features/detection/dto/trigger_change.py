"""Client -> server: the cells that settled differently from just before the throw."""

from pydantic import NonNegativeInt, PositiveInt

from app.api.core.dto.base import CamelModel


class TriggerChangeDto(CamelModel):
    col: NonNegativeInt
    row: NonNegativeInt
    cols: PositiveInt
    rows: PositiveInt
