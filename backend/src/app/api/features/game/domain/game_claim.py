"""The token that lets the device which set up an anonymous game hand it to an account."""

import hashlib
import secrets
from enum import Enum


class ClaimOutcome(Enum):
    CLAIMED = "claimed"
    NOT_FOUND = "not_found"
    BAD_SEAT = "bad_seat"


def new_claim_token() -> str:
    return secrets.token_urlsafe(32)


def claim_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
