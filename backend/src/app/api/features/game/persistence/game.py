"""The game itself. Its turns and darts hang off it in their own tables."""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, uuid_primary_key


class GameTable(Base):
    __tablename__ = "games"

    id: Mapped[str] = uuid_primary_key()
    mode: Mapped[int] = mapped_column(Integer)
    variant: Mapped[str] = mapped_column(String(16))
    checkout_mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    current_player_index: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    evaluation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tracker_version: Mapped[int | None] = mapped_column(Integer, default=None)
    # The open visit's shadow darts as {value, multiplier, position}; only that visit has any.
    shadow_darts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Touched on every write, so a game that nobody has come back to can be told
    # from one still being played.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
