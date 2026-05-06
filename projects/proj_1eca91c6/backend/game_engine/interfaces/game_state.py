"""
Game state management interfaces.

Defines the core interfaces for managing game sessions and states
across all game types in the Game Studio framework.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class GameState(Enum):
    """Generic game states applicable to all game types.

    States:
        IDLE: Initial state, session created but not initialized
        READY: Game initialized and ready to start
        RUNNING: Game actively running
        PAUSED: Game paused by player
        GAME_OVER: Game ended with win/loss condition
        ERROR: Game encountered an error
    """
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    ERROR = "error"


@dataclass
class GameSession:
    """Generic game session metadata.

    Attributes:
        session_id: Unique identifier for the session
        game_type: Type of game (e.g., "snake", "tetris")
        player_id: Identifier for the player
        created_at: Timestamp when session was created
        state: Current game state
        score: Current player score
        metadata: Additional game-specific data
        config: Configuration used for this session
    """
    session_id: str
    game_type: str
    player_id: str
    created_at: datetime
    state: GameState = GameState.IDLE
    score: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary representation."""
        return {
            "session_id": self.session_id,
            "game_type": self.game_type,
            "player_id": self.player_id,
            "created_at": self.created_at.isoformat(),
            "state": self.state.value,
            "score": self.score,
            "metadata": self.metadata,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameSession":
        """Create session from dictionary representation."""
        return cls(
            session_id=data["session_id"],
            game_type=data["game_type"],
            player_id=data["player_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            state=GameState(data["state"]),
            score=data.get("score", 0),
            metadata=data.get("metadata", {}),
            config=data.get("config", {}),
        )


class IGameStateManager(ABC):
    """Interface for game state management.

    This interface defines the contract for managing game sessions,
    including creation, retrieval, updates, and deletion. Implementations
    can use different storage backends (in-memory, Redis, database, etc.).
    """

    @abstractmethod
    async def create_session(
        self,
        game_type: str,
        player_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> GameSession:
        """Create a new game session.

        Args:
            game_type: Type of game to create
            player_id: Identifier for the player
            config: Optional game configuration

        Returns:
            Created game session

        Raises:
            ValueError: If game_type is not supported
            RuntimeError: If session creation fails
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get a game session by ID.

        Args:
            session_id: Unique session identifier

        Returns:
            Game session if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[GameState]:
        """Get current game state.

        Args:
            session_id: Unique session identifier

        Returns:
            Current game state if session exists, None otherwise
        """
        pass

    @abstractmethod
    async def update_state(
        self,
        session_id: str,
        state_update: Dict[str, Any]
    ) -> bool:
        """Update game session data.

        Args:
            session_id: Unique session identifier
            state_update: Dictionary containing fields to update

        Returns:
            True if update was successful, False otherwise
        """
        pass

    @abstractmethod
    async def transition_state(
        self,
        session_id: str,
        new_state: GameState
    ) -> bool:
        """Transition to a new game state.

        Args:
            session_id: Unique session identifier
            new_state: Target game state

        Returns:
            True if transition was successful, False otherwise
        """
        pass

    @abstractmethod
    async def update_score(self, session_id: str, score: int) -> bool:
        """Update player score.

        Args:
            session_id: Unique session identifier
            score: New score value

        Returns:
            True if update was successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a game session.

        Args:
            session_id: Unique session identifier

        Returns:
            True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def list_sessions(
        self,
        game_type: Optional[str] = None,
        player_id: Optional[str] = None
    ) -> List[GameSession]:
        """List game sessions with optional filters.

        Args:
            game_type: Filter by game type
            player_id: Filter by player ID

        Returns:
            List of matching game sessions
        """
        pass
