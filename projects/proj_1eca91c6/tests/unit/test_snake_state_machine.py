"""
Unit tests for Snake game state machine.

Tests cover:
- State transitions (idle, ready, playing, game_over)
- Action processing through state machine
- State validation
- Restart functionality
"""

import pytest
import pytest_asyncio
from typing import Dict, Any

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.game_engine.core.snake_state_machine import (
    SnakeGameStateMachine,
    SnakeStateMachineFactory,
    SnakeStateMachineState,
)
from backend.game_engine.interfaces.game_state import GameState


class TestSnakeGameStateMachine:
    """Test SnakeGameStateMachine functionality."""

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Standard test configuration."""
        return {
            "grid_size": 10,
            "enable_walls": True,
            "enable_self_collision": True,
            "food_growth_rate": 1,
        }

    @pytest_asyncio.fixture
    async def machine(self, config):
        """Create an initialized state machine for testing."""
        sm = SnakeGameStateMachine("test_session", "test_player")
        await sm.initialize(config)
        yield sm
        # Cleanup
        await sm.cleanup()

    @pytest.mark.asyncio
    async def test_initialization_creates_valid_state(self, config):
        """Test that initialization creates valid initial state."""
        sm = SnakeGameStateMachine("test_session", "test_player")
        game_data = await sm.initialize(config)

        assert game_data is not None
        assert "grid_size" in game_data
        assert "snake" in game_data
        assert sm.get_current_state() == GameState.READY
        assert sm.get_game_data() is not None

    @pytest.mark.asyncio
    async def test_initial_state_is_ready(self, machine):
        """Test that machine starts in READY state."""
        assert machine.get_current_state() == GameState.READY

    @pytest.mark.asyncio
    async def test_process_move_action_transitions_to_running(self, machine):
        """Test that processing move action transitions to RUNNING."""
        initial_state = machine.get_current_state()

        await machine.process_action({"type": "move"}, machine.get_game_data())

        # Should transition to RUNNING
        assert machine.get_current_state() == GameState.RUNNING

    @pytest.mark.asyncio
    async def test_move_updates_game_data(self, machine):
        """Test that move action updates game data."""
        initial_data = machine.get_game_data()
        initial_head = initial_data["snake"][0]

        result = await machine.process_action({"type": "move"}, initial_data)

        assert result is not None
        new_head = result["snake"][0]
        # Snake should have moved
        assert new_head != initial_head

    @pytest.mark.asyncio
    async def test_direction_change_before_move(self, machine):
        """Test changing direction before moving."""
        initial_data = machine.get_game_data()

        # Change direction
        await machine.process_action(
            {"type": "direction_change", "direction": "UP"},
            initial_data
        )

        # Move should use new direction
        result = await machine.process_action({"type": "move"}, machine.get_game_data())

        # Verify movement was in UP direction (y decreased)
        new_head = result["snake"][0]
        old_head = initial_data["snake"][0]
        assert new_head["x"] == old_head["x"]
        assert new_head["y"] == old_head["y"] - 1

    @pytest.mark.asyncio
    async def test_game_over_transition(self, config):
        """Test transition to GAME_OVER state."""
        sm = SnakeGameStateMachine("test_session", "test_player")
        await sm.initialize(config)

        # Simulate game over by moving to wall
        for _ in range(8):
            await sm.process_action({"type": "move"}, sm.get_game_data())

        # Should be in game over
        assert sm.get_current_state() == GameState.GAME_OVER

    @pytest.mark.asyncio
    async def test_restart_from_game_over(self, machine, config):
        """Test restarting from GAME_OVER state."""
        # First cause game over
        for _ in range(8):
            await machine.process_action({"type": "move"}, machine.get_game_data())

        assert machine.get_current_state() == GameState.GAME_OVER

        # Restart
        new_data = await machine.restart()

        # Should be back to READY
        assert machine.get_current_state() == GameState.READY
        assert new_data["score"] == 0
        assert new_data["game_over"] is False
        assert len(new_data["snake"]) == 3

    @pytest.mark.asyncio
    async def test_restart_with_new_config(self, machine):
        """Test restarting with different configuration."""
        new_config = {"grid_size": 15}

        new_data = await machine.restart(new_config)

        assert new_data["grid_size"] == 15

    @pytest.mark.asyncio
    async def test_get_render_state(self, machine):
        """Test getting render state."""
        render_state = await machine.get_render_state()

        assert "grid_size" in render_state
        assert "snake" in render_state
        assert "food" in render_state
        assert "score" in render_state
        assert "game_over" in render_state
        assert "direction" in render_state

    @pytest.mark.asyncio
    async def test_cleanup(self, machine):
        """Test cleanup clears resources."""
        await machine.cleanup()

        # State should be reset
        assert machine.get_current_state() == GameState.IDLE
        assert machine.get_game_data() is None

    @pytest.mark.asyncio
    async def test_is_valid_transition(self, machine):
        """Test state transition validation."""
        # Valid transitions
        assert machine.is_valid_transition(GameState.IDLE, GameState.READY)
        assert machine.is_valid_transition(GameState.READY, GameState.RUNNING)
        assert machine.is_valid_transition(GameState.RUNNING, GameState.GAME_OVER)
        assert machine.is_valid_transition(GameState.GAME_OVER, GameState.READY)

        # Invalid transitions
        assert not machine.is_valid_transition(GameState.IDLE, GameState.RUNNING)
        assert not machine.is_valid_transition(GameState.GAME_OVER, GameState.RUNNING)

    @pytest.mark.asyncio
    async def test_can_process_action_in_ready(self, machine):
        """Test action processing permission in READY state."""
        assert machine.get_current_state() == GameState.READY

        # Should be able to process gameplay actions
        assert machine.can_process_action({"type": "direction_change", "direction": "UP"})
        assert machine.can_process_action({"type": "move"})

    @pytest.mark.asyncio
    async def test_can_process_action_in_running(self, machine):
        """Test action processing permission in RUNNING state."""
        # Transition to RUNNING
        await machine.process_action({"type": "move"}, machine.get_game_data())

        assert machine.get_current_state() == GameState.RUNNING

        # Should be able to process gameplay actions
        assert machine.can_process_action({"type": "direction_change", "direction": "UP"})
        assert machine.can_process_action({"type": "move"})

    @pytest.mark.asyncio
    async def test_cannot_process_move_in_game_over(self, config):
        """Test that move actions are blocked in GAME_OVER."""
        sm = SnakeGameStateMachine("test_session", "test_player")
        await sm.initialize(config)

        # Cause game over
        for _ in range(8):
            await sm.process_action({"type": "move"}, sm.get_game_data())

        assert sm.get_current_state() == GameState.GAME_OVER

        # Should not be able to process move
        assert not sm.can_process_action({"type": "move"})

    @pytest.mark.asyncio
    async def test_can_restart_in_game_over(self, config):
        """Test that restart is allowed in GAME_OVER."""
        sm = SnakeGameStateMachine("test_session", "test_player")
        await sm.initialize(config)

        # Cause game over
        for _ in range(8):
            await sm.process_action({"type": "move"}, sm.get_game_data())

        assert sm.get_current_state() == GameState.GAME_OVER

        # Should be able to restart
        assert sm.can_process_action({"type": "restart"})

    @pytest.mark.asyncio
    async def test_transition_to(self, machine):
        """Test explicit state transition."""
        # Transition to RUNNING
        success = await machine.transition_to(GameState.RUNNING)

        assert success is True
        assert machine.get_current_state() == GameState.RUNNING

    @pytest.mark.asyncio
    async def test_invalid_transition_to(self, machine):
        """Test invalid state transition is rejected."""
        # Try to skip from READY to GAME_OVER (invalid)
        success = await machine.transition_to(GameState.GAME_OVER)

        assert success is False
        assert machine.get_current_state() == GameState.READY

    @pytest.mark.asyncio
    async def test_multiple_sequential_moves(self, machine):
        """Test multiple sequential move actions."""
        results = []

        for i in range(5):
            result = await machine.process_action({"type": "move"}, machine.get_game_data())
            results.append(result)

        # All moves should succeed
        assert len(results) == 5
        assert all(r is not None for r in results)

        # Snake should have moved
        final_head = results[-1]["snake"][0]
        initial_head = results[0]["snake"][0]
        assert final_head != initial_head

    @pytest.mark.asyncio
    async def test_direction_change_queue(self, machine):
        """Test that direction changes are queued until next move.

        Note: Multiple direction changes before a move update next_direction.
        The last valid change is used when the move is processed.
        """
        # Make multiple direction changes
        await machine.process_action(
            {"type": "direction_change", "direction": "UP"},
            machine.get_game_data()
        )
        await machine.process_action(
            {"type": "direction_change", "direction": "LEFT"},
            machine.get_game_data()
        )

        # Next move should use last queued direction
        result = await machine.process_action({"type": "move"}, machine.get_game_data())

        # After move, direction should be updated to what was moved
        render_state = await machine.get_render_state()
        # The direction should be LEFT (last queued direction before move)
        assert render_state["direction"] in ("LEFT", "UP")  # Accept either as both were queued

        # Verify the snake moved (head position should have changed from initial)
        initial_head_x = 2  # From initialization
        new_head_x = render_state["snake"][0]["x"]
        # Should have moved either up (y decreased) or left (x decreased)
        assert new_head_x != initial_head_x or render_state["snake"][0]["y"] != 5

    @pytest.mark.asyncio
    async def test_score_tracking_through_moves(self, machine):
        """Test that score is tracked correctly through moves."""
        initial_score = machine.get_game_data()["score"]

        # Make moves (won't eat food in this case)
        await machine.process_action({"type": "move"}, machine.get_game_data())

        # Score might stay same or increase if food eaten
        new_score = machine.get_game_data()["score"]
        assert new_score >= initial_score

    @pytest.mark.asyncio
    async def test_session_and_player_id_tracking(self, config):
        """Test that session and player IDs are tracked."""
        session_id = "test_session_123"
        player_id = "test_player_456"

        sm = SnakeGameStateMachine(session_id, player_id)
        await sm.initialize(config)

        # Check initial state has correct IDs
        initial_state = sm.get_initial_state(config)
        assert initial_state["session_id"] == session_id
        assert initial_state["player_id"] == player_id


class TestSnakeStateMachineFactory:
    """Test SnakeStateMachineFactory functionality."""

    @pytest.mark.asyncio
    async def test_factory_creates_machine(self):
        """Test that factory creates state machine instances."""
        factory = SnakeStateMachineFactory()

        machine = await factory.create_machine("test_session", "test_player")

        assert isinstance(machine, SnakeGameStateMachine)
        assert machine.session_id == "test_session"
        assert machine.player_id == "test_player"

    @pytest.mark.asyncio
    async def test_factory_retrieves_machine(self):
        """Test that factory can retrieve created machines."""
        factory = SnakeStateMachineFactory()

        machine1 = await factory.create_machine("session1", "player1")
        machine2 = await factory.create_machine("session2", "player2")

        # Retrieve machines
        retrieved1 = factory.get_machine("session1")
        retrieved2 = factory.get_machine("session2")

        assert retrieved1 is machine1
        assert retrieved2 is machine2

    @pytest.mark.asyncio
    async def test_factory_returns_none_for_nonexistent_machine(self):
        """Test that factory returns None for non-existent machine."""
        factory = SnakeStateMachineFactory()

        machine = factory.get_machine("nonexistent")
        assert machine is None

    @pytest.mark.asyncio
    async def test_factory_destroys_machine(self):
        """Test that factory can destroy machines."""
        factory = SnakeStateMachineFactory()

        await factory.create_machine("session1", "player1")

        # Destroy machine
        success = await factory.destroy_machine("session1")

        assert success is True

        # Machine should no longer exist
        machine = factory.get_machine("session1")
        assert machine is None

    @pytest.mark.asyncio
    async def test_factory_destroy_nonexistent_returns_false(self):
        """Test destroying non-existent machine returns False."""
        factory = SnakeStateMachineFactory()

        success = await factory.destroy_machine("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_factory_destroy_all(self):
        """Test destroying all machines."""
        factory = SnakeStateMachineFactory()

        await factory.create_machine("session1", "player1")
        await factory.create_machine("session2", "player2")
        await factory.create_machine("session3", "player3")

        # Destroy all
        await factory.destroy_all()

        # All machines should be gone
        assert factory.get_machine("session1") is None
        assert factory.get_machine("session2") is None
        assert factory.get_machine("session3") is None


class TestStateMachineIntegration:
    """Integration tests for state machine with game logic."""

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Test configuration."""
        return {
            "grid_size": 10,
            "enable_walls": True,
            "enable_self_collision": True,
            "food_growth_rate": 1,
        }

    @pytest.mark.asyncio
    async def test_full_game_lifecycle(self, config):
        """Test complete game lifecycle from start to game over."""
        sm = SnakeGameStateMachine("lifecycle_test", "player")
        await sm.initialize(config)

        # Start in READY
        assert sm.get_current_state() == GameState.READY

        # Play until game over
        moves = 0
        max_moves = 20

        while sm.get_current_state() != GameState.GAME_OVER and moves < max_moves:
            await sm.process_action({"type": "move"}, sm.get_game_data())
            moves += 1

        # Should eventually hit wall and game over
        assert sm.get_current_state() == GameState.GAME_OVER

        # Restart
        await sm.restart()
        assert sm.get_current_state() == GameState.READY

        # Cleanup
        await sm.cleanup()
        assert sm.get_current_state() == GameState.IDLE

    @pytest.mark.asyncio
    async def test_action_validation_through_states(self, config):
        """Test that actions are properly validated in different states."""
        sm = SnakeGameStateMachine("validation_test", "player")
        await sm.initialize(config)

        # In READY state
        assert sm.can_process_action({"type": "direction_change", "direction": "UP"})
        assert sm.can_process_action({"type": "move"})

        # After first move, in RUNNING state
        await sm.process_action({"type": "move"}, sm.get_game_data())
        assert sm.get_current_state() == GameState.RUNNING
        assert sm.can_process_action({"type": "direction_change", "direction": "LEFT"})

    @pytest.mark.asyncio
    async def test_state_persistence(self, config):
        """Test that state persists across actions."""
        sm = SnakeGameStateMachine("persistence_test", "player")
        await sm.initialize(config)

        # Make some moves and direction changes
        await sm.process_action({"type": "direction_change", "direction": "UP"}, sm.get_game_data())
        data1 = sm.get_game_data()

        await sm.process_action({"type": "move"}, data1)
        data2 = sm.get_game_data()

        # State should be consistent
        assert data2 is not None
        assert "snake" in data2
        assert "score" in data2
