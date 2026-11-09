import asyncio
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.api.features.auth.domain.username import display_name_for, username_base
from app.api.features.auth.services import google_tokens

_GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_CLIENT_ID = "test-client.apps.googleusercontent.com"


@pytest.fixture(autouse=True)
def google_keys(monkeypatch):
    """Google's key set, reduced to the one key the tests sign with."""
    found = SimpleNamespace(key=_GOOGLE_KEY.public_key())
    monkeypatch.setattr(
        google_tokens, "_keys", SimpleNamespace(get_signing_key_from_jwt=lambda _: found)
    )
    monkeypatch.setattr(
        google_tokens, "get_settings", lambda: SimpleNamespace(google_client_id=_CLIENT_ID)
    )


def token(key=_GOOGLE_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": _CLIENT_ID,
        "sub": "1234",
        "email": " Alice@Gmail.com",
        "email_verified": True,
        "name": "Alice Liddell",
        "iat": now,
        "exp": now + 3600,
    } | overrides
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")


def verify(credential):
    return asyncio.run(google_tokens.verify(credential))


def test_a_token_google_signed_for_this_client_names_the_account():
    identity = verify(token())

    assert identity is not None
    assert (identity.subject, identity.email, identity.email_verified, identity.name) == (
        "1234",
        "alice@gmail.com",
        True,
        "Alice Liddell",
    )


def test_the_issuer_may_come_without_scheme():
    assert verify(token(iss="accounts.google.com")) is not None


@pytest.mark.parametrize(
    "credential",
    [
        pytest.param(token(key=_OTHER_KEY), id="foreign signature"),
        pytest.param(token(aud="someone-else.apps.googleusercontent.com"), id="other client"),
        pytest.param(token(iss="https://evil.example.org"), id="other issuer"),
        pytest.param(token(exp=int(time.time()) - 120), id="expired"),
        pytest.param(token(email=None), id="no address"),
        pytest.param("not a token", id="garbage"),
    ],
)
def test_anything_else_is_refused(credential):
    assert verify(credential) is None


def test_an_unconfirmed_address_is_reported_as_such():
    assert verify(token(email_verified=False)).email_verified is False


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("alice.liddell@gmail.com", "alice.liddell"),
        ("jörg+darts@gmail.com", "jrgdarts"),
        ("jo@gmail.com", "joplayer"),
        (f"{'a' * 40}@gmail.com", "a" * 32),
    ],
)
def test_username_base_keeps_to_the_username_rules(email, expected):
    assert username_base(email) == expected


def test_display_name_falls_back_to_the_address():
    assert display_name_for(None, "alice@gmail.com") == "alice"
    assert display_name_for("x" * 80, "alice@gmail.com") == "x" * 64
