"""Player identities, independent of accounts.

The two user columns answer different questions and only coincide for the
account holder: `user_id` says this player *is* that account and drives the
history, `owner_user_id` says who created the identity and drives the
autocomplete. Both stay NULL until M4.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.api.core.services.translations import translate
from app.infrastructure.database import Base, uuid_primary_key


class PlayerTable(Base):
    __tablename__ = "players"
    # One address book links an account at most once.
    __table_args__ = (UniqueConstraint("owner_user_id", "user_id"),)

    id: Mapped[str] = uuid_primary_key()
    # NULL once the account this entry stood for was deleted.
    display_name: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    # The address book a linked entry was taken out of; lets the linked account still find it.
    former_owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def shown_name(display_name: str | None) -> str:
    """A stored name as people see it: a deleted account's reads in the request's language."""
    return translate("player.deleted") if display_name is None else display_name
