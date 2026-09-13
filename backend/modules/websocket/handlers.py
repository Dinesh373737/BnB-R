"""
WebSocket Layer — Handlers
FastAPI WebSocket endpoints for the various real-time channels.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.common.logger import logger as log
from backend.modules.websocket.manager import ws_manager

router = APIRouter()

async def _handle_websocket(websocket: WebSocket, channel: str):
    """Generic handler for a websocket connection to a specific channel."""
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            # We primarily push data TO the client, but we must call receive()
            # so FastAPI/Uvicorn knows when the client disconnects.
            data = await websocket.receive_text()
            log.debug(f"Received client message on '{channel}': {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception as e:
        log.error(f"Unexpected WebSocket error on channel '{channel}': {e}")
        ws_manager.disconnect(websocket, channel)

@router.websocket("/ws/microgrid")
async def websocket_microgrid(websocket: WebSocket):
    """Endpoint for real-time microgrid state and power flow updates."""
    await _handle_websocket(websocket, "microgrid")

@router.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    """Endpoint for real-time AI agent decisions and internal logs."""
    await _handle_websocket(websocket, "agents")

@router.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    """Endpoint for real-time P2P energy market trades and clearing prices."""
    await _handle_websocket(websocket, "market")

from pydantic import BaseModel

class BroadcastPayload(BaseModel):
    channel: str
    message: dict

@router.post("/api/test-broadcast", tags=["WebSockets"])
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
