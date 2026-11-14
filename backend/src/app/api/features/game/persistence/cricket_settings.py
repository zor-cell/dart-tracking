"""The settings of a Cricket game."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class CricketSettingsTable(Base):
    __tablename__ = "game_cricket"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    scoring: Mapped[str] = mapped_column(String(16))
