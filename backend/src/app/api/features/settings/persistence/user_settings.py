"""One row of switches per account."""

from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, UuidText


class UserSettingsTable(Base):
    """The account id is the primary key: an account has exactly one set, and a
    deleted account takes it with it."""

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        UuidText, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    advance_on_pull: Mapped[bool] = mapped_column(Boolean)
    evaluation_enabled: Mapped[bool] = mapped_column(Boolean)
    preferred_doubles: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
