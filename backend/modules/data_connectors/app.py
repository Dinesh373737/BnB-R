"""
Data Connectors — Standalone App
Allows running and testing the Data Connectors module completely in isolation.
"""

from fastapi import FastAPI
from backend.modules.data_connectors.router import router

app = FastAPI(
    title="GridMind Data Connectors",
    description="Standalone Module for fetching external Weather and Grid data.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Welcome to the GridMind Data Connectors API. Visit /docs to test."}
