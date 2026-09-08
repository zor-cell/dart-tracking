"""The account, as the rest of the app sees it — without the password hash."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.auth.domain.user_role import UserRole


@dataclass(frozen=True)
class User:
    id: str
    email: str
    username: str
    created_at: datetime
    role: UserRole = UserRole.USER

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN
