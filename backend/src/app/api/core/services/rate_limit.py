"""Redis-backed counters that cap how often a caller may do something. Fixed
windows: the first hit starts one, the key's TTL ends it."""

import hashlib

from fastapi import HTTPException, Request, status

from app.infrastructure import redis_client


def client_ip(request: Request) -> str:
    """The caller's address, as uvicorn resolved it from the proxy headers."""
    return request.client.host if request.client else "unknown"


def _key(scope: str, subject: str) -> str:
    # Hashed, so no email address or IP sits in Redis in the clear.
    digest = hashlib.sha256(subject.encode()).hexdigest()[:32]
    return f"ratelimit:{scope}:{digest}"


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="too many requests",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


async def count(scope: str, subject: str, window_seconds: int) -> int:
    """Record one hit and return how many the current window holds."""
    key = _key(scope, subject)
    async with redis_client.client().pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        hits, _ = await pipe.execute()
    return int(hits)


async def check(scope: str, subject: str, limit: int) -> None:
    """429 if the current window already holds `limit` hits; records nothing."""
    key = _key(scope, subject)
    hits = await redis_client.client().get(key)
    if hits is not None and int(hits) >= limit:
        raise _too_many(await redis_client.client().ttl(key))


async def enforce(scope: str, subject: str, limit: int, window_seconds: int) -> None:
    """Record one hit; 429 once the window holds more than `limit`."""
    if await count(scope, subject, window_seconds) > limit:
        raise _too_many(await redis_client.client().ttl(_key(scope, subject)))


async def reset(scope: str, subject: str) -> None:
    await redis_client.client().delete(_key(scope, subject))
