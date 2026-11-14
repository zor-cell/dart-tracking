"""The settings of an x01 game."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class X01SettingsTable(Base):
    __tablename__ = "game_x01"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    start_score: Mapped[int] = mapped_column(Integer)
    checkout_mode: Mapped[str] = mapped_column(String(16))
    catch_up: Mapped[bool] = mapped_column(Boolean, default=False)
    play_on: Mapped[bool] = mapped_column(Boolean, default=False)
