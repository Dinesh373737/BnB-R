"""
Market Engine — Standalone App
Allows running and testing the Market Engine module completely in isolation.
"""

from fastapi import FastAPI
from backend.common.database import engine, Base
from backend.modules.market_engine.router import router

# Ensure tables are created in the database before starting
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GridMind Market Engine",
    description="Standalone P2P Energy Market Module for isolated testing.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Welcome to the GridMind Market Engine standalone API. Visit /docs to test."}
