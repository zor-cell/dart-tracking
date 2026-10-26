"""A filter an account picked in one of its lists, kept for the client to rank its
suggestions. The server stores these without reading them."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FilterUse:
    # The list it was picked in, e.g. "games"; key and value as the client names them.
    view: str
    key: str
    value: str
    # The client's weight for this pick, fading with time since `last_used_at`.
    score: float
    last_used_at: datetime
