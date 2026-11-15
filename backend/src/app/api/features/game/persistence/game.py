"""The game itself. Its settings, turns and darts hang off it in their own tables."""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, uuid_primary_key


class GameTable(Base):
    __tablename__ = "games"

    id: Mapped[str] = uuid_primary_key()
    # Names the table that holds the game's settings.
    variant: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    current_player_index: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    evaluation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tracking_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    win_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_darts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    # SHA-256 of the token the creating device holds to hand an anonymous game to an account.
    claim_token_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
