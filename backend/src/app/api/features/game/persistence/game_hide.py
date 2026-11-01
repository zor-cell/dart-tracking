"""The games an account took out of its own list and statistics."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, UuidText


class GameHideTable(Base):
    __tablename__ = "game_hides"

    user_id: Mapped[str] = mapped_column(
        UuidText, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    game_id: Mapped[str] = mapped_column(
        UuidText, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
