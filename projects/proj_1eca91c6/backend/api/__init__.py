"""
FastAPI application for Snake Game REST API.

This module provides REST endpoints for game session management,
player action submission, and state queries.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.routers import snake, games
from api.session_manager import SessionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Snake Game API",
    description="REST API for Snake Game MVP",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize session manager
session_manager = SessionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting Snake Game API...")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Snake Game API...")
    await session_manager.cleanup_all()


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Snake Game API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "snake": "/api/snake",
            "games": "/api/games"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(snake.router, prefix="/api/snake", tags=["Snake"])
app.include_router(games.router, prefix="/api/games", tags=["Games"])

# Make session manager available to routers
app.state.session_manager = session_manager
