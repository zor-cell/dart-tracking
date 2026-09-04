"""The account, as the rest of the app sees it — without the password hash."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: str
    email: str
    username: str
    created_at: datetime
