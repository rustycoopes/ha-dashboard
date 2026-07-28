from httpx import AsyncClient


async def test_health_returns_ok(no_db_client: AsyncClient) -> None:
    response = await no_db_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
