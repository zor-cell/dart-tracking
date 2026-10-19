from pydantic import Field

from app.api.core.dto.base import CamelModel


class GameCommandBase(CamelModel):
    """Client -> server: what every game command carries besides its own fields."""

    # Revision of the state the command was made against; None skips the check.
    revision: int | None = Field(default=None, ge=0)
