"""WebSocket endpoint for real-time workspace updates.

This is a basic implementation that provides a simple WebSocket connection
manager for broadcasting messages to connected clients. It does not currently
implement file watching or debouncing - those features are planned for future
iterations.

Current limitations:
- No automatic file watching or change detection
- No debouncing of broadcast messages
- No workspace-specific subscriptions
- Simple broadcast to all connected clients only
"""
from __future__ import annotations

from fastapi import WebSocket


class WebSocketManager:
    """Manage connected WebSocket clients for broadcasting messages."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Add a new connection."""
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a connection."""
        self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, object]) -> None:
        """Send a message to all connected clients."""
        if not self._connections:
            return

        # Remove disconnected clients
        disconnected = set()
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)

        # Clean up disconnected
        self._connections.difference_update(disconnected)


_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """Get the singleton WebSocket manager."""
    return _manager


async def broadcast_entity_changed(
    *,
    workspace: str,
    entity_type: str,
    entity_id: str,
    action: str,
) -> None:
    """Broadcast a normalized entity change event to connected clients."""
    await _manager.broadcast({
        "type": "entity_changed",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "workspace": workspace,
        "action": action,
    })
