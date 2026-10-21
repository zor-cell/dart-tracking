"""Single-use tokens behind links, stored in Redis until they expire. Each subject
holds at most one live token per namespace: issuing a new one voids the last."""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta

from app.infrastructure import redis_client


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Redeemed:
    subject: str
    payload: str | None


class OneTimeTokens:
    def __init__(self, namespace: str, ttl: timedelta) -> None:
        self._namespace = namespace
        self.ttl = ttl

    def _token_key(self, digest: str) -> str:
        return f"{self._namespace}:token:{digest}"

    def _subject_key(self, subject: str) -> str:
        return f"{self._namespace}:subject:{subject}"

    async def issue(self, subject: str, payload: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        digest = _digest(token)
        value = json.dumps({"subject": subject, "payload": payload})
        ttl = int(self.ttl.total_seconds())
        redis = redis_client.client()
        previous = await redis.get(self._subject_key(subject))
        async with redis.pipeline(transaction=True) as pipe:
            if previous is not None:
                pipe.delete(self._token_key(previous.decode()))
            pipe.set(self._token_key(digest), value, ex=ttl)
            pipe.set(self._subject_key(subject), digest, ex=ttl)
            await pipe.execute()
        return token

    async def peek(self, token: str) -> Redeemed | None:
        """What the token was issued for, without spending it."""
        value = await redis_client.client().get(self._token_key(_digest(token)))
        return _parse(value)

    async def consume(self, token: str) -> Redeemed | None:
        """What the token was issued for, or None if it is unknown, spent or expired."""
        redis = redis_client.client()
        redeemed = _parse(await redis.getdel(self._token_key(_digest(token))))
        if redeemed is not None:
            await redis.delete(self._subject_key(redeemed.subject))
        return redeemed


def _parse(value: bytes | None) -> Redeemed | None:
    if value is None:
        return None
    data = json.loads(value)
    subject = data.get("subject")
    return Redeemed(subject=subject, payload=data.get("payload")) if subject else None
