"""One step of a game as it happened. Append-only, never updated or deleted."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, UuidText


class GameEventTable(Base):
    """A plain sequence for the primary key, unlike the uuid ids elsewhere: the
    replay depends on the exact order the rows were written in."""

    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(
        UuidText, ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(String(20))
    turn_index: Mapped[int] = mapped_column(Integer)
    player_index: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[bool] = mapped_column(Boolean)
    camera_armed: Mapped[bool] = mapped_column(Boolean, default=False)
    client_id: Mapped[str | None] = mapped_column(String(64), default=None)
    value: Mapped[int | None] = mapped_column(Integer, default=None)
    multiplier: Mapped[int | None] = mapped_column(Integer, default=None)
    pos_x: Mapped[float | None] = mapped_column(Float, default=None)
    pos_y: Mapped[float | None] = mapped_column(Float, default=None)
    failure: Mapped[str | None] = mapped_column(String(32), default=None)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
