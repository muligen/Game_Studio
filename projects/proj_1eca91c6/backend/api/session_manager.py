"""
Session manager for Snake Game API.

Manages game session lifecycle and state using the state machine implementation.
"""

from typing import Dict, Optional, Any
from datetime import datetime
import uuid
import json
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from game_engine.core.snake_state_machine import SnakeGameStateMachine, SnakeStateMachineFactory
from game_engine.interfaces.game_state import GameState, GameSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages game sessions and their state machines."""

    def __init__(self):
        """Initialize session manager."""
        self._state_machine_factory = SnakeStateMachineFactory()
        self._sessions: Dict[str, GameSession] = {}
        self._state_machines: Dict[str, SnakeGameStateMachine] = {}

    async def create_session(
        self,
        game_type: str = "snake",
        player_id: str = "default",
        config: Optional[Dict[str, Any]] = None
    ) -> tuple[str, GameSession, Dict[str, Any]]:
        """Create a new game session.

        Args:
            game_type: Type of game (currently only "snake")
            player_id: Player identifier
            config: Optional game configuration

        Returns:
            Tuple of (session_id, session_info, initial_game_state)

        Raises:
            ValueError: If game_type is not supported
        """
        if game_type != "snake":
            raise ValueError(f"Unsupported game type: {game_type}")

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Create state machine
        state_machine = await self._state_machine_factory.create_machine(
            session_id=session_id,
            player_id=player_id
        )

        # Load configuration
        if config is None:
            config = self._get_default_config()

        # Initialize game
        initial_game_state = await state_machine.initialize(config)

        # Create session metadata
        session = GameSession(
            session_id=session_id,
            game_type=game_type,
            player_id=player_id,
            created_at=datetime.now(),
            state=GameState.READY,
            score=0,
            config=config
        )

        # Store session
        self._sessions[session_id] = session
        self._state_machines[session_id] = state_machine

        logger.info(f"Created session {session_id} for player {player_id}")

        return session_id, session, initial_game_state

    async def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get session metadata by ID.

        Args:
            session_id: Session identifier

        Returns:
            GameSession if found, None otherwise
        """
        return self._sessions.get(session_id)

    async def get_game_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current game state for session.

        Args:
            session_id: Session identifier

        Returns:
            Game state dictionary if found, None otherwise
        """
        state_machine = self._state_machines.get(session_id)
        if not state_machine:
            return None

        return state_machine.get_game_data()

    async def submit_move(
        self,
        session_id: str,
        direction: str
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Submit a direction change for the game.

        Args:
            session_id: Session identifier
            direction: Direction (UP, DOWN, LEFT, RIGHT)

        Returns:
            Tuple of (success, game_state, error_message)
        """
        state_machine = self._state_machines.get(session_id)
        session = self._sessions.get(session_id)

        if not state_machine or not session:
            return False, None, "Session not found"

        # Check if game is over
        if session.state == GameState.GAME_OVER:
            return False, None, "Game is over"

        # Check if session is in valid state
        if session.state not in (GameState.READY, GameState.RUNNING):
            return False, None, f"Cannot move in {session.state.value} state"

        # Submit direction change action
        action = {
            "type": "direction_change",
            "direction": direction.upper()
        }

        try:
            # Process action through state machine
            current_state = state_machine.get_game_data()
            result = await state_machine.process_action(action, current_state)

            # Update session state
            current_machine_state = state_machine.get_current_state()
            session.state = current_machine_state
            session.score = result.get("score", 0)

            return True, result, None

        except ValueError as e:
            return False, None, str(e)
        except Exception as e:
            logger.error(f"Error processing move: {e}")
            return False, None, "Internal error processing move"

    async def restart_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[GameSession], Optional[Dict[str, Any]], Optional[str]]:
        """Restart a game session.

        Args:
            session_id: Session identifier
            config: Optional new configuration

        Returns:
            Tuple of (success, session_info, game_state, error_message)
        """
        state_machine = self._state_machines.get(session_id)
        session = self._sessions.get(session_id)

        if not state_machine or not session:
            return False, None, None, "Session not found"

        try:
            # Restart game
            if config is None:
                config = session.config

            new_game_state = await state_machine.restart(config)

            # Update session
            session.state = GameState.READY
            session.score = 0
            session.config = config

            return True, session, new_game_state, None

        except Exception as e:
            logger.error(f"Error restarting session: {e}")
            return False, None, None, "Internal error restarting session"

    async def delete_session(self, session_id: str) -> bool:
        """Delete a game session and clean up resources.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False otherwise
        """
        if session_id not in self._sessions:
            return False

        # Clean up state machine
        await self._state_machine_factory.destroy_machine(session_id)

        # Remove session
        del self._sessions[session_id]

        logger.info(f"Deleted session {session_id}")

        return True

    async def cleanup_all(self) -> None:
        """Clean up all sessions and resources."""
        await self._state_machine_factory.destroy_all()
        self._sessions.clear()
        logger.info("Cleaned up all sessions")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default game configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "grid_size": 10,
            "initial_speed": 500,
            "enable_walls": True,
            "enable_self_collision": True,
            "food_growth_rate": 1,
        }

    def list_sessions(self) -> list[GameSession]:
        """List all active sessions.

        Returns:
            List of active GameSession objects
        """
        return list(self._sessions.values())
