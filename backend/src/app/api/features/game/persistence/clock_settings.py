"""The settings of an Around the Clock game."""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ClockSettingsTable(Base):
    __tablename__ = "game_around_the_clock"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    zone: Mapped[str] = mapped_column(String(16))
    skip: Mapped[bool] = mapped_column(Boolean, default=False)
    catch_up: Mapped[bool] = mapped_column(Boolean, default=False)
    play_on: Mapped[bool] = mapped_column(Boolean, default=False)
