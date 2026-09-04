"""One thrown dart."""

from sqlalchemy import Float, ForeignKeyConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, UuidText


class DartTable(Base):
    """`pos_x`/`pos_y` are board millimetres and stay NULL for a manually
    entered dart — they are the heatmap's raw data."""

    __tablename__ = "darts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "turn_index"],
            ["turns.game_id", "turns.turn_index"],
            ondelete="CASCADE",
        ),
    )

    game_id: Mapped[str] = mapped_column(UuidText, primary_key=True)
    turn_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    dart_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
    multiplier: Mapped[int] = mapped_column(Integer)
    pos_x: Mapped[float | None] = mapped_column(Float, default=None)
    pos_y: Mapped[float | None] = mapped_column(Float, default=None)
