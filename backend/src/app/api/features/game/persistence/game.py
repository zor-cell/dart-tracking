"""The game itself. Its turns and darts hang off it in their own tables."""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, uuid_primary_key


class GameTable(Base):
    __tablename__ = "games"

    id: Mapped[str] = uuid_primary_key()
    # Null outside the points variants, which keep their settings in `options`.
    mode: Mapped[int | None] = mapped_column(Integer)
    variant: Mapped[str] = mapped_column(String(16))
    checkout_mode: Mapped[str | None] = mapped_column(String(16))
    options: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    catch_up: Mapped[bool] = mapped_column(Boolean, default=False)
    play_on: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16))
    current_player_index: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    evaluation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tracking_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    win_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_darts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
