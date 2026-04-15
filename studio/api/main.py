from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from studio.api.routes import balance_tables, bugs, design_docs, logs, requirements


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Game Studio API",
        description="Web UI backend for Game Studio collaboration kernel",
        version="0.1.0",
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

    return app
