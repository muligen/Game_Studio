"""
General games API endpoints.

Provides endpoints for game configuration and general game information.
"""

from fastapi import APIRouter, HTTPException, status, Request
from typing import Dict, Any
import json
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.schemas import ConfigResponse, GameConfig

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{game_type}/config", response_model=ConfigResponse)
async def get_game_config(game_type: str, request: Request):
    """Get configuration schema and defaults for a game type.

    Returns the default configuration and constraints for the specified game.

    Args:
        game_type: Type of game (e.g., "snake")

    Returns:
        ConfigResponse with default configuration and constraints

    Raises:
        HTTPException: If game_type is not supported
    """
    if game_type != "snake":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unsupported_game",
                "message": f"Game type '{game_type}' is not supported"
            }
        )

    # Load configuration from file
    try:
        # This would typically load from a config file
        # For now, return hardcoded values
        config = GameConfig(
            grid_size=10,
            initial_speed=500,
            enable_walls=True,
            enable_self_collision=True,
            food_growth_rate=1
        )

        constraints = {
            "grid_size": {"type": "int", "range": [5, 30]},
            "initial_speed": {"type": "int", "range": [100, 2000]},
            "enable_walls": {"type": "bool"},
            "enable_self_collision": {"type": "bool"},
            "food_growth_rate": {"type": "int", "range": [1, 5]},
        }

        return ConfigResponse(
            game_type=game_type,
            config=config,
            constraints=constraints
        )

    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "config_error", "message": "Failed to load game configuration"}
        )


@router.get("/{game_type}/sessions")
async def list_sessions(game_type: str, request: Request):
    """List active game sessions for a game type.

    Args:
        game_type: Type of game to filter by

    Returns:
        List of active session IDs
    """
    if game_type != "snake":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unsupported_game",
                "message": f"Game type '{game_type}' is not supported"
            }
        )

    session_manager = request.app.state.session_manager
    sessions = session_manager.list_sessions()

    # Filter by game type and format response
    session_list = [
        {
            "session_id": s.session_id,
            "player_id": s.player_id,
            "state": s.state.value,
            "score": s.score,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
        if s.game_type == game_type
    ]

    return {
        "game_type": game_type,
        "count": len(session_list),
        "sessions": session_list
    }
