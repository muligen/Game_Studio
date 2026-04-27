from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from studio.api.routes import (
    balance_tables,
    bugs,
    clarifications,
    delivery,
    design_docs,
    logs,
    meetings,
    pool as pool_routes,
    requirements,
    workflows,
)
from studio.api.websocket import get_websocket_manager
from studio.runtime import pool
from studio.runtime.delivery_task_poller import DeliveryTaskPoller
from studio.runtime.poller import WorkflowPoller


@asynccontextmanager
async def _default_lifespan(app: FastAPI):
    """Start the workflow poller and delivery task poller in the background."""
    workspace_path = Path(".studio-data") / ".studio-data"
    workflow_poller = WorkflowPoller(workspace_path=workspace_path)
    delivery_task_poller = DeliveryTaskPoller(workspace_path=workspace_path)

    workflow_task = asyncio.create_task(workflow_poller.start())
    delivery_task = asyncio.create_task(delivery_task_poller.start())

    yield

    await workflow_poller.stop()
    await delivery_task_poller.stop()

    workflow_task.cancel()
    delivery_task.cancel()

    try:
        await workflow_task
    except asyncio.CancelledError:
        pass
    try:
        await delivery_task
    except asyncio.CancelledError:
        pass

    pool.shutdown()


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
    app.include_router(pool_routes.router, prefix="/api")
    app.include_router(meetings.router, prefix="/api")
    app.include_router(delivery.router, prefix="/api")
    app.include_router(clarifications.router, prefix="/api")

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
