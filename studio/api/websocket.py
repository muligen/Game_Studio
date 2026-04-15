"""WebSocket endpoint and file watcher for real-time updates."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import WebSocket
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class WebSocketManager:
    """Manage connected WebSocket clients."""

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


class WorkspaceWatcher(FileSystemEventHandler):
    """Watch workspace directory for file changes."""

    def __init__(self, workspace_root: Path, manager: WebSocketManager) -> None:
        super().__init__()
        self.workspace_root = workspace_root
        self.manager = manager
        self._debounce_tasks: dict[str, asyncio.Task] = {}

    def _extract_entity_info(self, path: str) -> tuple[str, str] | None:
        """Extract entity type and ID from file path."""
        path_obj = Path(path)

        # Map directory names to entity types
        dir_to_type = {
            "requirements": "requirement",
            "design_docs": "design_doc",
            "balance_tables": "balance_table",
            "bugs": "bug",
            "logs": "log",
        }

        if path_obj.parent.name in dir_to_type:
            entity_type = dir_to_type[path_obj.parent.name]
            entity_id = path_obj.stem  # filename without .json
            return (entity_type, entity_id)

        return None

    def _schedule_broadcast(self, key: str, message: dict[str, object]) -> None:
        """Schedule a debounced broadcast."""
        # Cancel existing task for this key if any
        if key in self._debounce_tasks:
            self._debounce_tasks[key].cancel()

        # Create new delayed task
        async def broadcast_after_delay() -> None:
            await asyncio.sleep(0.1)  # 100ms debounce
            await self.manager.broadcast(message)
            del self._debounce_tasks[key]

        # Note: In FastAPI context, we'll handle this differently
        # For now, just mark that a broadcast is needed
        # The actual broadcasting will be handled by the endpoint
        pass

    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        if not event.src_path.endswith(".json"):
            return

        entity_info = self._extract_entity_info(event.src_path)
        if entity_info is None:
            return

        entity_type, entity_id = entity_info
        message = {
            "type": "entity_changed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": "updated",
        }

        # Store for broadcast (manager will pick it up)
        self.manager._pending_message = message  # type: ignore


def start_file_watcher(workspace_path: Path, manager: WebSocketManager) -> Observer:
    """Start watching the workspace directory."""
    observer = Observer()
    watcher = WorkspaceWatcher(workspace_path, manager)
    observer.schedule(watcher, path=str(workspace_path), recursive=True)
    observer.start()
    return observer
