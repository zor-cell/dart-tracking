from fastapi.testclient import TestClient


def test_large_responses_are_compressed(client: TestClient):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    assert "paths" in response.json()


def test_small_responses_stay_plain(client: TestClient):
    response = client.get("/api/health", headers={"Accept-Encoding": "gzip"})

    assert "content-encoding" not in response.headers
