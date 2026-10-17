"""Redis-backed refresh tokens, one key per active session. Redis for the same
reason as the other hot stores: the TTL is the expiry, so nothing has to be
cleaned up."""

import hashlib
import secrets

from app.infrastructure import redis_client
from app.infrastructure.config import get_settings


def _digest(token: str) -> str:
    # Keys hold a digest, so a dump of the store hands out no usable token.
    return hashlib.sha256(token.encode()).hexdigest()


def _key(digest: str) -> str:
    return f"auth:refresh:{digest}"


def _sessions_key(user_id: str) -> str:
    """The set of token digests an account holds, for signing it out everywhere."""
    return f"auth:sessions:{user_id}"


class RefreshStore:
    async def issue(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        digest = _digest(token)
        ttl = get_settings().refresh_token_days * 24 * 60 * 60
        async with redis_client.client().pipeline(transaction=True) as pipe:
            pipe.set(_key(digest), user_id, ex=ttl)
            pipe.sadd(_sessions_key(user_id), digest)
            pipe.expire(_sessions_key(user_id), ttl)
            await pipe.execute()
        return token

    async def consume(self, token: str) -> str | None:
        """Redeem a token once: it is deleted as it is read, so rotation leaves
        no reusable predecessor and a replayed token finds nothing."""
        digest = _digest(token)
        user_id = await redis_client.client().getdel(_key(digest))
        if user_id is None:
            return None
        await redis_client.client().srem(_sessions_key(user_id.decode()), digest)
        return user_id.decode()

    async def revoke(self, token: str) -> None:
        await self.consume(token)

    async def revoke_all(self, user_id: str) -> None:
        redis = redis_client.client()
        digests = await redis.smembers(_sessions_key(user_id))
        keys = [_key(digest.decode()) for digest in digests]
        await redis.delete(*keys, _sessions_key(user_id))


store = RefreshStore()
