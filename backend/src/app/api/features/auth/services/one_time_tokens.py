"""Single-use tokens for links sent by mail, stored in Redis until they expire.
Each account holds at most one live token per purpose: issuing a new one voids the last."""

import hashlib
import json
import secrets
from dataclasses import dataclass

from app.infrastructure import redis_client


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Redeemed:
    user_id: str
    payload: str | None


class OneTimeTokens:
    def __init__(self, purpose: str, ttl_seconds: int) -> None:
        self._purpose = purpose
        self.ttl_seconds = ttl_seconds

    def _token_key(self, digest: str) -> str:
        return f"auth:{self._purpose}:token:{digest}"

    def _user_key(self, user_id: str) -> str:
        return f"auth:{self._purpose}:user:{user_id}"

    async def issue(self, user_id: str, payload: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        digest = _digest(token)
        value = json.dumps({"userId": user_id, "payload": payload})
        redis = redis_client.client()
        previous = await redis.get(self._user_key(user_id))
        async with redis.pipeline(transaction=True) as pipe:
            if previous is not None:
                pipe.delete(self._token_key(previous.decode()))
            pipe.set(self._token_key(digest), value, ex=self.ttl_seconds)
            pipe.set(self._user_key(user_id), digest, ex=self.ttl_seconds)
            await pipe.execute()
        return token

    async def consume(self, token: str) -> Redeemed | None:
        """What the token was issued for, or None if it is unknown, spent or expired."""
        redis = redis_client.client()
        value = await redis.getdel(self._token_key(_digest(token)))
        if value is None:
            return None
        data = json.loads(value)
        await redis.delete(self._user_key(data["userId"]))
        return Redeemed(user_id=data["userId"], payload=data["payload"])


email_verification = OneTimeTokens("verify-email", 24 * 60 * 60)
password_reset = OneTimeTokens("password-reset", 60 * 60)
email_change = OneTimeTokens("email-change", 24 * 60 * 60)
