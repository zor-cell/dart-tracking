"""Redis-backed refresh tokens, one key per active session. Redis for the same
reason as the other hot stores: the TTL is the expiry, so nothing has to be
cleaned up (docs/feature/done/persistenz.md §2.2)."""

import hashlib
import secrets

from app.infrastructure import redis_client
from app.infrastructure.config import get_settings


def _key(token: str) -> str:
    # The key is a digest, so a dump of the store hands out no usable token.
    return f"auth:refresh:{hashlib.sha256(token.encode()).hexdigest()}"


class RefreshStore:
    async def issue(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        await redis_client.client().set(
            _key(token), user_id, ex=get_settings().refresh_token_days * 24 * 60 * 60
        )
        return token

    async def consume(self, token: str) -> str | None:
        """Redeem a token once: it is deleted as it is read, so rotation leaves
        no reusable predecessor and a replayed token finds nothing."""
        user_id = await redis_client.client().getdel(_key(token))
        return None if user_id is None else user_id.decode()

    async def revoke(self, token: str) -> None:
        await redis_client.client().delete(_key(token))


store = RefreshStore()
