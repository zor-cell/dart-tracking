"""The settings of a personal training, with the plan it was started on."""

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class PersonalSettingsTable(Base):
    __tablename__ = "game_personal"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    focus: Mapped[str] = mapped_column(String(16))
    length: Mapped[int] = mapped_column(Integer)
    any_ring: Mapped[bool] = mapped_column(Boolean, default=True)
    # Each block as {"fields": [[value, multiplier], …], "darts": n}, in throwing order.
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Each planned field's record before, as {"field": [value, multiplier], "darts", "hits"}.
    baselines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
