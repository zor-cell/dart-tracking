"""Account table. Nothing writes to it before M3; it exists so the nullable
user columns on `players` and `games` can carry a foreign key."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.api.features.auth.domain.user_role import UserRole
from app.infrastructure.database import Base, uuid_primary_key


class UserTable(Base):
    """`email` is what one signs in with, `username` is the unique handle a guest
    player can later be handed over to; `display_name` is the name the player
    list shows and is not unique."""

    __tablename__ = "users"

    id: Mapped[str] = uuid_primary_key()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), server_default=UserRole.USER.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
