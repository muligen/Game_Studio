"""
LangGraph-based state machine for Snake game.

This module implements the game state machine using LangGraph, managing
state transitions between idle, ready, playing, paused, and game_over states.
"""

from typing import Dict, Any, Optional, TypedDict, Annotated, Sequence
from enum import Enum
import operator

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from backend.game_engine.interfaces.game_state import GameState
from backend.game_engine.core.snake_logic import SnakeGameLogic, SnakeGameData


class SnakeStateMachineState(TypedDict):
    """State for LangGraph state machine."""
    # Session metadata
    session_id: str
    game_state: str  # GameState value as string
    player_id: str

    # Game data
    game_data: Optional[Dict[str, Any]]

    # Action processing
    current_action: Optional[Dict[str, Any]]
    action_result: Optional[Dict[str, Any]]

    # Configuration
    config: Dict[str, Any]

    # Error handling
    error: Optional[str]

    # Messages (for LangGraph message passing)
    messages: Annotated[Sequence[str], operator.add]


class SnakeGameStateMachine:
    """LangGraph-based state machine for Snake game orchestration."""

    # State transition mappings
    STATE_TRANSITIONS = {
        GameState.IDLE: [GameState.READY],
        GameState.READY: [GameState.RUNNING, GameState.IDLE],
        GameState.RUNNING: [GameState.PAUSED, GameState.GAME_OVER, GameState.READY],
        GameState.PAUSED: [GameState.RUNNING, GameState.GAME_OVER],
        GameState.GAME_OVER: [GameState.READY, GameState.IDLE],
        GameState.ERROR: [GameState.IDLE],
    }

    def __init__(self, session_id: str, player_id: str = "default"):
        """Initialize the state machine.

        Args:
            session_id: Unique session identifier
            player_id: Player identifier
        """
        self.session_id = session_id
        self.player_id = player_id
        self.game_logic = SnakeGameLogic()
        self._graph: Optional[StateGraph] = None
        self._initial_state: Optional[SnakeStateMachineState] = None
        self._current_state: Optional[GameState] = None

    def get_initial_state(self, config: Dict[str, Any]) -> SnakeStateMachineState:
        """Get initial state machine state.

        Args:
            config: Game configuration

        Returns:
            Initial state machine state
        """
        return {
            "session_id": self.session_id,
            "game_state": GameState.IDLE.value,
            "player_id": self.player_id,
            "game_data": None,
            "current_action": None,
            "action_result": None,
            "config": config,
            "error": None,
            "messages": [],
        }

    async def initialize(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the game state machine.

        Args:
            config: Game configuration

        Returns:
            Initial game state data
        """
        self._initial_state = self.get_initial_state(config)
        self._current_state = GameState.IDLE

        # Initialize game logic
        game_data = await self.game_logic.initialize(config, self.session_id)

        # Transition to READY state
        self._current_state = GameState.READY
        self._initial_state["game_state"] = GameState.READY.value
        self._initial_state["game_data"] = game_data

        return game_data

    async def process_action(
        self,
        action: Dict[str, Any],
        current_state_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process an action through the state machine.

        Args:
            action: Action to process
            current_state_data: Current game data

        Returns:
            Resulting game state
        """
        # Update current state reference
        if current_state_data:
            self._initial_state["game_data"] = current_state_data

        # Ensure we're in RUNNING state for gameplay actions
        if self._current_state not in (GameState.READY, GameState.RUNNING):
            return self._initial_state.get("game_data", {})

        # Transition to RUNNING if in READY
        if self._current_state == GameState.READY:
            self._current_state = GameState.RUNNING

        # Process action through game logic
        result = await self.game_logic.process_action(self.session_id, action)
        self._initial_state["game_data"] = result

        # Check for game over
        is_over, reason = await self.game_logic.check_game_over(
            self.session_id, result
        )

        if is_over:
            self._current_state = GameState.GAME_OVER
            self._initial_state["game_state"] = GameState.GAME_OVER.value

        return result

    async def restart(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Restart the game.

        Args:
            config: Optional new configuration

        Returns:
            New game state data
        """
        if config is None:
            config = self._initial_state.get("config", {})

        # Reset state machine
        self._current_state = GameState.READY

        # Reinitialize game logic
        game_data = await self.game_logic.initialize(config, self.session_id)
        self._initial_state["game_data"] = game_data
        self._initial_state["game_state"] = GameState.READY.value
        self._initial_state["error"] = None

        return game_data

    def get_current_state(self) -> GameState:
        """Get current game state.

        Returns:
            Current GameState enum value
        """
        return self._current_state or GameState.IDLE

    def get_game_data(self) -> Optional[Dict[str, Any]]:
        """Get current game data.

        Returns:
            Current game data dictionary
        """
        return self._initial_state.get("game_data") if self._initial_state else None

    async def get_render_state(self) -> Dict[str, Any]:
        """Get render-ready state.

        Returns:
            Render state dictionary
        """
        game_data = self.get_game_data()
        if not game_data:
            return {}

        return await self.game_logic.get_render_state(self.session_id, game_data)

    async def cleanup(self) -> None:
        """Clean up state machine resources."""
        await self.game_logic.cleanup(self.session_id)
        self._current_state = GameState.IDLE
        self._initial_state = None

    def is_valid_transition(self, from_state: GameState, to_state: GameState) -> bool:
        """Check if state transition is valid.

        Args:
            from_state: Source state
            to_state: Destination state

        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = self.STATE_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets

    def can_process_action(self, action: Dict[str, Any]) -> bool:
        """Check if action can be processed in current state.

        Args:
            action: Action to check

        Returns:
            True if action can be processed, False otherwise
        """
        current = self.get_current_state()
        action_type = action.get("type", "")

        # Only allow gameplay actions in READY or RUNNING states
        if action_type in ("direction_change", "move"):
            return current in (GameState.READY, GameState.RUNNING)

        # Allow restart in GAME_OVER state
        if action_type == "restart":
            return current == GameState.GAME_OVER

        return False

    async def transition_to(self, new_state: GameState) -> bool:
        """Transition to a new state.

        Args:
            new_state: Target state

        Returns:
            True if transition was successful, False otherwise
        """
        current = self.get_current_state()

        if not self.is_valid_transition(current, new_state):
            return False

        self._current_state = new_state
        if self._initial_state:
            self._initial_state["game_state"] = new_state.value

        return True


class SnakeStateMachineFactory:
    """Factory for creating Snake game state machines."""

    def __init__(self):
        """Initialize factory."""
        self._machines: Dict[str, SnakeGameStateMachine] = {}

    async def create_machine(
        self,
        session_id: str,
        player_id: str = "default"
    ) -> SnakeGameStateMachine:
        """Create a new state machine instance.

        Args:
            session_id: Unique session identifier
            player_id: Player identifier

        Returns:
            New SnakeGameStateMachine instance
        """
        machine = SnakeGameStateMachine(session_id, player_id)
        self._machines[session_id] = machine
        return machine

    def get_machine(self, session_id: str) -> Optional[SnakeGameStateMachine]:
        """Get existing state machine by session ID.

        Args:
            session_id: Session identifier

        Returns:
            SnakeGameStateMachine if found, None otherwise
        """
        return self._machines.get(session_id)

    async def destroy_machine(self, session_id: str) -> bool:
        """Destroy a state machine instance.

        Args:
            session_id: Session identifier

        Returns:
            True if machine was found and destroyed, False otherwise
        """
        machine = self._machines.pop(session_id, None)
        if machine:
            await machine.cleanup()
            return True
        return False

    async def destroy_all(self) -> None:
        """Destroy all state machines."""
        for session_id, machine in list(self._machines.items()):
            await machine.cleanup()
        self._machines.clear()
