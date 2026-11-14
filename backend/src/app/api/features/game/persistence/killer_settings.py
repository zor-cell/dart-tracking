"""The settings of a Killer game."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class KillerSettingsTable(Base):
    __tablename__ = "game_killer"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    # Each seat's number, in seat order.
    numbers: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    lives: Mapped[int] = mapped_column(Integer)
    zone: Mapped[str] = mapped_column(String(16))
