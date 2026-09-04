"""Short-lived bearer tokens: signed, stateless, and never revoked before they
expire — that is what the refresh token's rotation is for (refresh_store.py)."""

from datetime import UTC, datetime, timedelta

import jwt

from app.infrastructure.config import get_settings

_ALGORITHM = "HS256"


def issue(user_id: str) -> tuple[str, int]:
    """The token and its lifetime in seconds, so the client can refresh ahead
    of the expiry instead of waiting for a 401."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_minutes)
    issued_at = datetime.now(UTC)
    token = jwt.encode(
        {"sub": user_id, "iat": issued_at, "exp": issued_at + lifetime},
        settings.jwt_secret,
        algorithm=_ALGORITHM,
    )
    return token, int(lifetime.total_seconds())


def read_subject(token: str) -> str | None:
    """The user id the token was issued for, or None if it does not hold up."""
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    subject = claims.get("sub")
    return subject if isinstance(subject, str) else None
