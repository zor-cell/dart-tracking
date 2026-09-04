"""Account table. Nothing writes to it before M3; it exists so the nullable
user columns on `players` and `games` can carry a foreign key."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, uuid_primary_key


class UserTable(Base):
    """`email` is what one signs in with; `username` is the public handle a
    guest player can later be handed over to without revealing the address."""

    __tablename__ = "users"

    id: Mapped[str] = uuid_primary_key()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
