from app.api.core.dto.base import CamelModel


class RegisterDartRequest(CamelModel):
    points: int
