"""
API request and response schemas for Snake Game.

Defines Pydantic models for type-safe API communication.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum


class Direction(str, Enum):
    """Direction for snake movement."""
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class GameState(str, Enum):
    """Game state enumeration."""
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    ERROR = "error"


class Position(BaseModel):
    """2D grid position."""
    x: int = Field(..., ge=0, description="X coordinate")
    y: int = Field(..., ge=0, description="Y coordinate")


class GameConfig(BaseModel):
    """Game configuration parameters."""
    grid_size: int = Field(default=10, ge=5, le=30, description="Grid size (NxN)")
    initial_speed: int = Field(default=500, ge=100, le=2000, description="Speed in ms per tick")
    enable_walls: bool = Field(default=True, description="Enable wall collisions")
    enable_self_collision: bool = Field(default=True, description="Enable self collisions")
    food_growth_rate: int = Field(default=1, ge=1, le=5, description="Snake growth per food")


class GameSessionInfo(BaseModel):
    """Game session metadata."""
    session_id: str = Field(..., description="Unique session identifier")
    game_type: str = Field(..., description="Type of game")
    player_id: str = Field(default="default", description="Player identifier")
    created_at: str = Field(..., description="ISO format creation timestamp")
    state: GameState = Field(..., description="Current game state")
    score: int = Field(default=0, ge=0, description="Current score")


class SnakeGameData(BaseModel):
    """Complete snake game state."""
    grid_size: int = Field(..., ge=5, description="Grid dimension")
    snake: List[Position] = Field(..., min_length=1, description="Snake body segments")
    food: Optional[Position] = Field(None, description="Current food position")
    direction: str = Field(..., description="Current movement direction")
    score: int = Field(default=0, ge=0, description="Current score")
    game_over: bool = Field(default=False, description="Game over flag")
    game_over_reason: Optional[str] = Field(None, description="Reason for game over")


# Request Schemas

class StartGameRequest(BaseModel):
    """Request to start a new game."""
    player_id: Optional[str] = Field(default="default", description="Player identifier")
    config: Optional[GameConfig] = Field(None, description="Game configuration")


class MoveRequest(BaseModel):
    """Request to change snake direction."""
    direction: Direction = Field(..., description="New direction")
    session_id: str = Field(..., min_length=1, description="Session identifier")

    @field_validator('direction')
    @classmethod
    def direction_must_be_valid(cls, v):
        """Validate direction is a valid enum value."""
        if v not in Direction:
            raise ValueError("Invalid direction")
        return v


class RestartRequest(BaseModel):
    """Request to restart a game session."""
    session_id: str = Field(..., min_length=1, description="Session identifier")
    config: Optional[GameConfig] = Field(None, description="Optional new configuration")


# Response Schemas

class StartGameResponse(BaseModel):
    """Response from starting a new game."""
    session_id: str = Field(..., description="Session identifier")
    session_info: GameSessionInfo = Field(..., description="Session metadata")
    game_state: SnakeGameData = Field(..., description="Initial game state")


class GameStateResponse(BaseModel):
    """Response with current game state."""
    session_id: str = Field(..., description="Session identifier")
    session_info: GameSessionInfo = Field(..., description="Session metadata")
    game_state: SnakeGameData = Field(..., description="Current game state")


class MoveResponse(BaseModel):
    """Response from move submission."""
    session_id: str = Field(..., description="Session identifier")
    success: bool = Field(..., description="Whether move was accepted")
    game_state: Optional[SnakeGameData] = Field(None, description="Updated game state")
    message: Optional[str] = Field(None, description="Optional message")


class RestartResponse(BaseModel):
    """Response from restart request."""
    session_id: str = Field(..., description="Session identifier")
    session_info: GameSessionInfo = Field(..., description="Updated session info")
    game_state: SnakeGameData = Field(..., description="New game state")


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class ConfigResponse(BaseModel):
    """Response with game configuration."""
    game_type: str = Field(..., description="Game type identifier")
    config: GameConfig = Field(..., description="Default configuration")
    constraints: Dict[str, Any] = Field(..., description="Configuration constraints")
