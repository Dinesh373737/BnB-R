"""
WebSocket Layer — Standalone App
Provides an isolated FastAPI app for testing WebSocket connections via Uvicorn.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.modules.websocket.handlers import router
from backend.modules.websocket.manager import ws_manager
from pydantic import BaseModel

app = FastAPI(
    title="GridMind WebSocket Layer (Isolated Test)",
    description="Standalone app for testing real-time WebSocket broadcasting."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BroadcastPayload(BaseModel):
    channel: str
    message: dict

@app.post("/api/test-broadcast")
async def trigger_broadcast(payload: BroadcastPayload):
    """
    Utility REST endpoint for testing. 
    Send a POST request here with JSON to instantly broadcast it to all WebSocket clients!
    """
    await ws_manager.broadcast(payload.channel, payload.message)
    return {
        "status": "success",
        "action": "broadcasted",
        "channel": payload.channel
    }

app.include_router(router)
