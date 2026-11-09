from app.api.core.dto.base import CamelModel


class GoogleConfigDto(CamelModel):
    """What the browser needs to show Google's sign-in button."""

    client_id: str
