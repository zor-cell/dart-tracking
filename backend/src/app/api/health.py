from fastapi import APIRouter, Response, status

from app.infrastructure import database, redis_client

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check(response: Response) -> dict[str, object]:
    """Reports every backing service, and answers 503 as soon as one of them is
    unreachable."""
    services = {
        "database": await database.ping(),
        "redis": await redis_client.ping(),
    }
    healthy = all(services.values())

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "online" if healthy else "degraded", "services": services}
