from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.deps import get_session
from app.models import Item
from app.schemas import ItemCreate, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])

@router.post("", response_model=ItemResponse)
async def create_item(
    item_in: ItemCreate, session: AsyncSession = Depends(get_session)
):
    new_item = Item(name=item_in.name)
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item

@router.get("", response_model=List[ItemResponse])
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Item))
    return list(result.scalars().all())
