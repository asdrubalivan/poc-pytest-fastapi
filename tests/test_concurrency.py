import pytest
import asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_concurrent_creates(client: AsyncClient):
    async def create_item(idx):
        response = await client.post("/items", json={"name": f"Concurrent_{idx}"})
        assert response.status_code == 200
        return response.json()
    
    # Run 20 requests concurrently
    results = await asyncio.gather(*(create_item(i) for i in range(20)))
    assert len(results) == 20
    
    # List items
    response = await client.get("/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 20
