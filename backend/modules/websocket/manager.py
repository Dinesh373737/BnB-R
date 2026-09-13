"""
WebSocket Layer — Manager
Manages active WebSocket connections and broadcasting.
"""

from typing import Dict, List
from fastapi import WebSocket
from backend.common.logger import logger as log


class ConnectionManager:
    """Manages WebSocket connections and channel subscriptions."""
    
    def __init__(self):
        # Maps channel name to a list of connected WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {
            "microgrid": [],
            "agents": [],
            "market": []
        }

    async def connect(self, websocket: WebSocket, channel: str):
        """Accepts a new connection and assigns it to a channel."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        log.info(f"Client connected to WebSocket channel: '{channel}'")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Removes a disconnected client from a channel."""
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
            log.info(f"Client disconnected from WebSocket channel: '{channel}'")

    async def broadcast(self, channel: str, message: dict):
        """Broadcasts a JSON message to all clients subscribed to a specific channel."""
        if channel in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    log.warning(f"Failed to send message on channel '{channel}', removing dead connection: {e}")
                    dead_connections.append(connection)
            
            # Clean up connections that dropped abruptly
            for dead in dead_connections:
                self.disconnect(dead, channel)

# Singleton manager to be used across handlers
ws_manager = ConnectionManager()
