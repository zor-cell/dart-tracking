"""Player identities, independent of accounts.

The two user columns answer different questions and only coincide for the
account holder: `user_id` says this player *is* that account and drives the
history, `owner_user_id` says who created the identity and drives the
autocomplete. Both stay NULL until M4 (see docs/feature/persistenz.md §4.1).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, uuid_primary_key


class PlayerTable(Base):
    __tablename__ = "players"

    id: Mapped[str] = uuid_primary_key()
    display_name: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
