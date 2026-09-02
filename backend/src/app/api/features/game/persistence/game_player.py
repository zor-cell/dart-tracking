"""Who plays on which position in a game."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class GamePlayerTable(Base):
    """`player_index` is the domain's `Player.id`: the position the turns point
    at, and the same value as `games.current_player_index`."""

    __tablename__ = "game_players"
    __table_args__ = (UniqueConstraint("game_id", "player_id"),)

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    player_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
