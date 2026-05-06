"""
WebSocket connection manager for real-time game state updates.

Manages WebSocket connections and broadcasts game state updates to connected clients.
"""

from typing import Dict, Set
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for game state broadcasts."""

    def __init__(self):
        """Initialize connection manager."""
        # Session ID -> Set of active WebSocket connections
        self._session_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> Session ID mapping for reverse lookup
        self._connection_sessions: Dict[WebSocket, str] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Connect a WebSocket to a game session.

        Args:
            websocket: WebSocket connection
            session_id: Game session identifier

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await websocket.accept()

            async with self._lock:
                if session_id not in self._session_connections:
                    self._session_connections[session_id] = set()

                self._session_connections[session_id].add(websocket)
                self._connection_sessions[websocket] = session_id

            logger.info(f"WebSocket connected to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            return False

    async def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket connection.

        Args:
            websocket: WebSocket connection to disconnect
        """
        async with self._lock:
            session_id = self._connection_sessions.get(websocket)

            if session_id and session_id in self._session_connections:
                self._session_connections[session_id].discard(websocket)

                # Clean up empty session sets
                if not self._session_connections[session_id]:
                    del self._session_connections[session_id]

            self._connection_sessions.pop(websocket, None)

        logger.info(f"WebSocket disconnected from session {session_id}")

    async def broadcast_to_session(self, session_id: str, message: dict, exclude_ws: WebSocket = None) -> int:
        """Broadcast a message to all connections in a session.

        Args:
            session_id: Game session identifier
            message: Message dictionary to broadcast
            exclude_ws: Optional WebSocket to exclude from broadcast (typically the sender)

        Returns:
            Number of clients the message was sent to
        """
        async with self._lock:
            connections = self._session_connections.get(session_id, set()).copy()

        if not connections:
            return 0

        # Exclude specified WebSocket from broadcast
        if exclude_ws:
            connections.discard(exclude_ws)

        if not connections:
            return 0

        # Prepare message
        message_str = json.dumps(message)
        send_count = 0

        # Send to all connected clients
        for connection in connections:
            try:
                await connection.send_text(message_str)
                send_count += 1
            except Exception as e:
                logger.warning(f"Failed to send message to client: {e}")
                # Remove broken connection
                await self.disconnect(connection)

        return send_count

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> bool:
        """Send a message to a specific WebSocket connection.

        Args:
            message: Message dictionary to send
            websocket: WebSocket connection to send to

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            message_str = json.dumps(message)
            await websocket.send_text(message_str)
            return True
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            await self.disconnect(websocket)
            return False

    def get_connection_count(self, session_id: str) -> int:
        """Get the number of active connections for a session.

        Args:
            session_id: Game session identifier

        Returns:
            Number of active connections
        """
        return len(self._session_connections.get(session_id, set()))

    def get_total_connections(self) -> int:
        """Get the total number of active WebSocket connections.

        Returns:
            Total number of active connections
        """
        return len(self._connection_sessions)

    def get_active_sessions(self) -> Set[str]:
        """Get set of session IDs with active WebSocket connections.

        Returns:
            Set of active session IDs
        """
        return set(self._session_connections.keys())


# Global connection manager instance
connection_manager = ConnectionManager()
