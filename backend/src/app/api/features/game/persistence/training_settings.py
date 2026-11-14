"""The settings of a free training."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class TrainingSettingsTable(Base):
    __tablename__ = "game_training"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    goal: Mapped[str] = mapped_column(String(16))
    ring: Mapped[str] = mapped_column(String(16))
    # The own fields as [value, multiplier] pairs, in the order they come up.
    fields: Mapped[list[list[int]]] = mapped_column(JSONB, default=list)
    repeats: Mapped[int] = mapped_column(Integer, default=1)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)
    seed: Mapped[int] = mapped_column(Integer, default=0)
