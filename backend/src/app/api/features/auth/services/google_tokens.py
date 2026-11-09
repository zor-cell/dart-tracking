"""Checks the ID tokens the Google sign-in button hands the browser."""

import asyncio

import jwt

from app.api.features.auth.domain.google_identity import GoogleIdentity
from app.infrastructure.config import get_settings

_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True)


def _decode(credential: str) -> dict[str, object]:
    key = _keys.get_signing_key_from_jwt(credential)
    return jwt.decode(
        credential,
        key.key,
        algorithms=["RS256"],
        audience=get_settings().google_client_id,
        options={"require": ["exp", "iss", "sub", "aud"]},
        leeway=30,
    )


async def verify(credential: str) -> GoogleIdentity | None:
    """The identity in a token signed by Google for this client, or None."""
    try:
        claims = await asyncio.to_thread(_decode, credential)
    except (jwt.PyJWTError, OSError):
        return None

    subject, email = claims.get("sub"), claims.get("email")
    if claims.get("iss") not in _ISSUERS or not isinstance(subject, str) or not isinstance(email, str):
        return None
    name = claims.get("name")
    return GoogleIdentity(
        subject=subject,
        email=email.strip().lower(),
        email_verified=claims.get("email_verified") is True,
        name=(name.strip() or None) if isinstance(name, str) else None,
    )
