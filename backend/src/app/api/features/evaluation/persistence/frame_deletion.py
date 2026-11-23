"""A game whose kept frames are still to be deleted. No foreign key: the game row
may already be gone."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, UuidText


class FrameDeletionTable(Base):
    __tablename__ = "frame_deletions"

    game_id: Mapped[str] = mapped_column(UuidText, primary_key=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
