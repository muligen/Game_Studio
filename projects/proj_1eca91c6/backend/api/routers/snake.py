"""
Snake game specific API endpoints.

Provides endpoints for game initialization, state queries,
move submission, and session management.
"""

from fastapi import APIRouter, HTTPException, status, Request
from typing import Dict, Any
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.schemas import (
    StartGameRequest,
    StartGameResponse,
    MoveRequest,
    MoveResponse,
    RestartRequest,
    RestartResponse,
    GameStateResponse,
    ErrorResponse,
    Direction,
    GameConfig
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=StartGameResponse, status_code=status.HTTP_201_CREATED)
async def start_game(request: Request, body: StartGameRequest):
    """Initialize a new Snake game session.

    Creates a new game session with the specified configuration
    and returns the initial game state.

    Args:
        body: Request containing optional player_id and config

    Returns:
        StartGameResponse with session_id, session_info, and initial game_state

    Raises:
        HTTPException: If session creation fails
    """
    session_manager = request.app.state.session_manager

    try:
        # Convert config to dict if provided
        config = None
        if body.config:
            config = {
                "grid_size": body.config.grid_size,
                "initial_speed": body.config.initial_speed,
                "enable_walls": body.config.enable_walls,
                "enable_self_collision": body.config.enable_self_collision,
                "food_growth_rate": body.config.food_growth_rate,
            }

        # Create session
        session_id, session_info, initial_state = await session_manager.create_session(
            game_type="snake",
            player_id=body.player_id or "default",
            config=config
        )

        # Format response
        return StartGameResponse(
            session_id=session_id,
            session_info={
                "session_id": session_info.session_id,
                "game_type": session_info.game_type,
                "player_id": session_info.player_id,
                "created_at": session_info.created_at.isoformat(),
                "state": session_info.state.value,
                "score": session_info.score,
            },
            game_state=initial_state
        )

    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_config", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "session_creation_failed", "message": "Failed to create game session"}
        )


@router.get("/state/{session_id}", response_model=GameStateResponse)
async def get_game_state(session_id: str, request: Request):
    """Get current game state for a session.

    Retrieves the current game state including snake position,
    food location, score, and game status.

    Args:
        session_id: Game session identifier

    Returns:
        GameStateResponse with session_info and current game_state

    Raises:
        HTTPException: If session is not found
    """
    session_manager = request.app.state.session_manager

    # Get session info
    session_info = await session_manager.get_session(session_id)
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "session_not_found", "message": f"Session {session_id} not found"}
        )

    # Get game state
    game_state = await session_manager.get_game_state(session_id)
    if not game_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "state_not_found", "message": f"Game state for session {session_id} not found"}
        )

    return GameStateResponse(
        session_id=session_id,
        session_info={
            "session_id": session_info.session_id,
            "game_type": session_info.game_type,
            "player_id": session_info.player_id,
            "created_at": session_info.created_at.isoformat(),
            "state": session_info.state.value,
            "score": session_info.score,
        },
        game_state=game_state
    )


@router.post("/move", response_model=MoveResponse)
async def submit_move(body: MoveRequest, request: Request):
    """Submit a direction change for the Snake.

    Changes the snake's movement direction for the next tick.
    Invalid moves (180° turns) are rejected.

    Args:
        body: Request containing session_id and direction

    Returns:
        MoveResponse indicating success and updated game_state

    Raises:
        HTTPException: If session is not found or move is invalid
    """
    session_manager = request.app.state.session_manager

    # Validate session exists
    session = await session_manager.get_session(body.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "session_not_found", "message": f"Session {body.session_id} not found"}
        )

    # Submit move
    success, game_state, error_message = await session_manager.submit_move(
        session_id=body.session_id,
        direction=body.direction.value
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_move", "message": error_message or "Invalid move"}
        )

    return MoveResponse(
        session_id=body.session_id,
        success=True,
        game_state=game_state,
        message=None
    )


@router.post("/restart", response_model=RestartResponse)
async def restart_game(body: RestartRequest, request: Request):
    """Restart a game session.

    Resets the game to initial state while keeping the same session ID.
    Optionally accepts new configuration.

    Args:
        body: Request containing session_id and optional config

    Returns:
        RestartResponse with session_info and new game_state

    Raises:
        HTTPException: If session is not found
    """
    session_manager = request.app.state.session_manager

    # Validate session exists
    session = await session_manager.get_session(body.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "session_not_found", "message": f"Session {body.session_id} not found"}
        )

    # Convert config to dict if provided
    config = None
    if body.config:
        config = {
            "grid_size": body.config.grid_size,
            "initial_speed": body.config.initial_speed,
            "enable_walls": body.config.enable_walls,
            "enable_self_collision": body.config.enable_self_collision,
            "food_growth_rate": body.config.food_growth_rate,
        }

    # Restart session
    success, session_info, game_state, error_message = await session_manager.restart_session(
        session_id=body.session_id,
        config=config
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "restart_failed", "message": error_message or "Failed to restart game"}
        )

    return RestartResponse(
        session_id=body.session_id,
        session_info={
            "session_id": session_info.session_id,
            "game_type": session_info.game_type,
            "player_id": session_info.player_id,
            "created_at": session_info.created_at.isoformat(),
            "state": session_info.state.value,
            "score": session_info.score,
        },
        game_state=game_state
    )
