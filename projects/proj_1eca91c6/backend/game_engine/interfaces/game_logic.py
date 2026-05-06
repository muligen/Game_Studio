"""
Game logic interfaces.

Defines the contract for game-specific business logic that all
game implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from enum import Enum


class ActionType(Enum):
    """Standard action types for games."""
    MOVE = "move"
    ACTION = "action"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"
    QUIT = "quit"


class IGameLogic(ABC):
    """Interface for game-specific logic.

    All game types must implement this interface to provide their
    business logic, including initialization, action processing,
    validation, and rendering state preparation.
    """

    @abstractmethod
    async def initialize(
        self,
        config: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """Initialize game with configuration.

        Args:
            config: Game configuration parameters
            session_id: Unique session identifier

        Returns:
            Initial game data (e.g., board state, player position)

        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If initialization fails
        """
        pass

    @abstractmethod
    async def process_action(
        self,
        session_id: str,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process player action and return new state.

        Args:
            session_id: Unique session identifier
            action: Action data containing type and parameters

        Returns:
            Updated game data after processing action

        Raises:
            ValueError: If action is invalid
            RuntimeError: If action processing fails
        """
        pass

    @abstractmethod
    async def validate_action(
        self,
        session_id: str,
        action: Dict[str, Any]
    ) -> bool:
        """Validate if action is legal.

        Args:
            session_id: Unique session identifier
            action: Action data to validate

        Returns:
            True if action is valid, False otherwise
        """
        pass

    @abstractmethod
    async def check_game_over(
        self,
        session_id: str,
        game_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if game is over.

        Args:
            session_id: Unique session identifier
            game_data: Current game data

        Returns:
            Tuple of (is_over, reason) where:
                - is_over: True if game is over
                - reason: Optional reason for game over
        """
        pass

    @abstractmethod
    async def get_render_state(
        self,
        session_id: str,
        game_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get state formatted for rendering.

        Args:
            session_id: Unique session identifier
            game_data: Current game data

        Returns:
            Render-ready state dictionary for frontend
        """
        pass

    async def cleanup(self, session_id: str) -> None:
        """Clean up resources for a session.

        Args:
            session_id: Unique session identifier

        Note:
            Default implementation does nothing. Override if needed.
        """
        pass

    async def get_score(self, game_data: Dict[str, Any]) -> int:
        """Extract score from game data.

        Args:
            game_data: Current game data

        Returns:
            Current score

        Note:
            Default implementation looks for 'score' key.
            Override for custom scoring.
        """
        return game_data.get("score", 0)


class IGameLogicFactory(ABC):
    """Factory interface for creating game logic instances.

    This enables the plugin architecture where game types can be
    dynamically loaded and instantiated.
    """

    @abstractmethod
    def create(self) -> IGameLogic:
        """Create a new game logic instance.

        Returns:
            New game logic instance
        """
        pass

    @abstractmethod
    def get_game_type(self) -> str:
        """Get the game type this factory produces.

        Returns:
            Game type identifier (e.g., "snake", "tetris")
        """
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Get the game logic version.

        Returns:
            Version string
        """
        pass
