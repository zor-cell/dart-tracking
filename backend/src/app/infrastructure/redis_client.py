"""Async Redis client, opened on startup and closed on shutdown."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

_client: Redis | None = None


def init(url: str) -> None:
    global _client
    # Values stay bytes; each store decides its own encoding.
    _client = Redis.from_url(url, decode_responses=False)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


def client() -> Redis:
    if _client is None:
        raise RuntimeError("redis not initialised")
    return _client


async def ping() -> bool:
    """Whether the server answers (health check)."""
    if _client is None:
        return False
    try:
        return bool(await _client.ping())
    except (RedisError, OSError):
        return False
