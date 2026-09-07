"""One visit to the oche."""

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class TurnTable(Base):
    """`turn_index` counts the visits of the whole game, `player_index` says who
    threw this one — the position, not the player identity, which is what
    `game_players` resolves."""

    __tablename__ = "game_turns"

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_index: Mapped[int] = mapped_column(Integer)
    busted: Mapped[bool] = mapped_column(Boolean)
