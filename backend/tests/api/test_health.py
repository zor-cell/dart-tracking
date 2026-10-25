from app.infrastructure import redis_client


def test_health_reports_every_service(anon):
    response = anon.get("/health")
    assert (response.status_code, response.json()) == (
        200,
        {"status": "online", "services": {"database": True, "redis": True}},
    )


def test_one_service_down_degrades_the_health(anon, monkeypatch):
    async def unreachable() -> bool:
        return False

    monkeypatch.setattr(redis_client, "ping", unreachable)
    response = anon.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "services": {"database": True, "redis": False}}
