"""Who a Google ID token says the caller is."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    name: str | None
