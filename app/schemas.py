import datetime
from pydantic import BaseModel, ConfigDict

class ItemCreate(BaseModel):
    name: str

class ItemResponse(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
