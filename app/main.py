from fastapi import FastAPI
from app.routes import items
from app.db import engine
from app.models import Base

app = FastAPI(title="pytest-xdist DB POC")

app.include_router(items.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
