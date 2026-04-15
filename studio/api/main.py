from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from studio.api.routes import balance_tables, bugs, design_docs, logs, requirements, workflows
from studio.api.websocket import get_websocket_manager
from studio.runtime.poller import WorkflowPoller


@asynccontextmanager
async def _default_lifespan(app: FastAPI):
    """Start the workflow poller in the background."""
    workspace_path = Path(".studio-data")
    poller = WorkflowPoller(workspace_path=workspace_path)
    task = asyncio.create_task(poller.start())
    yield
    await poller.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Game Studio API",
        description="Web UI backend for Game Studio collaboration kernel",
        version="0.1.0",
        lifespan=_default_lifespan,
    )

    # Configure CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative React port
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Register API routes
    app.include_router(requirements.router, prefix="/api")
    app.include_router(design_docs.router, prefix="/api")
    app.include_router(balance_tables.router, prefix="/api")
    app.include_router(bugs.router, prefix="/api")
    app.include_router(logs.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")

    # WebSocket endpoint for real-time updates
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time updates."""
        manager = get_websocket_manager()
        await manager.connect(websocket)

        try:
            # Send connected message
            await websocket.send_json({"type": "connected"})

            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "subscribe":
                    # Subscribe to workspace updates
                    # TODO: Implement file watcher for automatic change detection
                    # For now, just acknowledge the subscription
                    workspace = data.get("workspace", ".studio-data")
                    await websocket.send_json({
                        "type": "subscribed",
                        "workspace": workspace
                    })

        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
