from datetime import datetime

from app.api.core.dto.base import CamelModel
from app.api.features.auth.domain.user import User
from app.api.features.auth.domain.user_role import UserRole


class UserDto(CamelModel):
    id: str
    email: str
    username: str
    display_name: str
    created_at: datetime
    role: UserRole
    email_verified: bool
    has_password: bool
    google_linked: bool

    @classmethod
    def from_entity(cls, user: User) -> "UserDto":
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            created_at=user.created_at,
            role=user.role,
            email_verified=user.email_verified,
            has_password=user.has_password,
            google_linked=user.google_linked,
        )
