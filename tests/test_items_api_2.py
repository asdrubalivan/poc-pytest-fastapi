import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

@pytest.mark.parametrize("i", range(50))
async def test_create_and_list_items(client: AsyncClient, i: int):
    # Create item
    response = await client.post("/items", json={"name": f"Item_{i}"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == f"Item_{i}"
    assert "id" in data
    assert "created_at" in data
    
    # List items
    response = await client.get("/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["name"] == f"Item_{i}"
