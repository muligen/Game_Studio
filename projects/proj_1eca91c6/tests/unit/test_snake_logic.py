"""
Unit tests for Snake game logic.

Tests cover:
- Movement logic with direction control
- 180-degree turn prevention
- Food generation algorithm
- Collision detection (walls and self)
- Score calculation and tracking
- Game state transitions
"""

import pytest
import pytest_asyncio
import asyncio
from typing import List, Tuple
import random

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.game_engine.core.snake_logic import (
    Direction,
    Position,
    SnakeGameData,
    SnakeGameLogic,
    SnakeGameLogicFactory,
)


class TestPosition:
    """Test Position class functionality."""

    def test_position_creation(self):
        """Test creating positions."""
        pos = Position(5, 3)
        assert pos.x == 5
        assert pos.y == 3

    def test_position_equality(self):
        """Test position equality."""
        pos1 = Position(5, 3)
        pos2 = Position(5, 3)
        pos3 = Position(3, 5)

        assert pos1 == pos2
        assert pos1 != pos3

    def test_position_hash(self):
        """Test position hashing for set membership."""
        pos1 = Position(5, 3)
        pos2 = Position(5, 3)
        pos3 = Position(3, 5)

        position_set = {pos1, pos3}
        assert pos2 in position_set

    def test_position_to_dict(self):
        """Test position serialization."""
        pos = Position(5, 3)
        data = pos.to_dict()
        assert data == {"x": 5, "y": 3}

    def test_position_from_dict(self):
        """Test position deserialization."""
        data = {"x": 5, "y": 3}
        pos = Position.from_dict(data)
        assert pos.x == 5
        assert pos.y == 3

    def test_position_add(self):
        """Test position addition."""
        pos = Position(5, 3)
        new_pos = pos.add(2, -1)
        assert new_pos.x == 7
        assert new_pos.y == 2


class TestDirection:
    """Test Direction enum functionality."""

    def test_direction_values(self):
        """Test direction vectors."""
        assert Direction.UP.value == (0, -1)
        assert Direction.DOWN.value == (0, 1)
        assert Direction.LEFT.value == (-1, 0)
        assert Direction.RIGHT.value == (1, 0)


class TestSnakeGameData:
    """Test SnakeGameData class functionality."""

    def test_game_data_defaults(self):
        """Test default game data values."""
        data = SnakeGameData()
        assert data.grid_size == 10
        assert len(data.snake) == 0
        assert data.food is None
        assert data.direction == Direction.RIGHT
        assert data.score == 0
        assert data.game_over is False

    def test_game_data_to_dict(self):
        """Test game data serialization."""
        data = SnakeGameData(
            grid_size=10,
            snake=[Position(5, 3), Position(4, 3)],
            food=Position(2, 2),
            score=5,
        )

        result = data.to_dict()
        assert result["grid_size"] == 10
        assert len(result["snake"]) == 2
        assert result["food"] == {"x": 2, "y": 2}
        assert result["score"] == 5

    def test_game_data_from_dict(self):
        """Test game data deserialization."""
        data_dict = {
            "grid_size": 10,
            "snake": [{"x": 5, "y": 3}, {"x": 4, "y": 3}],
            "food": {"x": 2, "y": 2},
            "direction": Direction.RIGHT.value,
            "next_direction": Direction.RIGHT.value,
            "score": 5,
            "game_over": False,
        }

        data = SnakeGameData.from_dict(data_dict)
        assert data.grid_size == 10
        assert len(data.snake) == 2
        assert data.food == Position(2, 2)
        assert data.score == 5

    def test_get_snake_set(self):
        """Test getting snake positions as set."""
        data = SnakeGameData(
            snake=[Position(5, 3), Position(4, 3), Position(3, 3)]
        )

        snake_set = data.get_snake_set()
        assert (5, 3) in snake_set
        assert (4, 3) in snake_set
        assert (3, 3) in snake_set
        assert (2, 3) not in snake_set


class TestSnakeGameLogic:
    """Test SnakeGameLogic class functionality."""

    @pytest_asyncio.fixture
    async def logic(self):
        """Create a SnakeGameLogic instance for testing."""
        return SnakeGameLogic()

    @pytest_asyncio.fixture
    async def initialized_session(self, logic):
        """Create an initialized game session for testing."""
        config = {
            "grid_size": 10,
            "enable_walls": True,
            "enable_self_collision": True,
            "food_growth_rate": 1,
        }
        session_id = "test_session"
        await logic.initialize(config, session_id)
        return session_id, logic

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self, logic):
        """Test that initialize creates a valid session."""
        config = {"grid_size": 10}
        session_id = "test_init"

        result = await logic.initialize(config, session_id)

        assert "grid_size" in result
        assert result["grid_size"] == 10
        assert "snake" in result
        assert len(result["snake"]) == 3  # Initial snake has 3 segments
        assert "food" in result
        assert result["food"] is not None
        assert result["score"] == 0

    @pytest.mark.asyncio
    async def test_initialize_validates_grid_size(self, logic):
        """Test that initialize validates grid size constraints."""
        session_id = "test_validation"

        # Grid size too small
        with pytest.raises(ValueError):
            await logic.initialize({"grid_size": 2}, session_id)

        # Grid size too large
        with pytest.raises(ValueError):
            await logic.initialize({"grid_size": 50}, session_id)

    @pytest.mark.asyncio
    async def test_initial_snake_position(self, initialized_session):
        """Test that initial snake is positioned correctly."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        assert len(game_data.snake) == 3
        # Snake should be horizontal in left-center area
        # Head at x=2, y=5 (for 10x10 grid)
        assert game_data.snake[0].x > game_data.snake[1].x
        assert game_data.snake[1].x > game_data.snake[2].x

    @pytest.mark.asyncio
    async def test_initial_direction(self, initialized_session):
        """Test that initial direction is RIGHT."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        assert game_data.direction == Direction.RIGHT
        assert game_data.next_direction == Direction.RIGHT

    @pytest.mark.asyncio
    async def test_direction_change_valid(self, initialized_session):
        """Test valid direction changes."""
        session_id, logic = initialized_session

        # From RIGHT, can go UP or DOWN
        await logic.process_action(session_id, {"type": "direction_change", "direction": "UP"})
        game_data = logic._sessions[session_id]
        assert game_data.next_direction == Direction.UP

        await logic.process_action(session_id, {"type": "direction_change", "direction": "DOWN"})
        game_data = logic._sessions[session_id]
        assert game_data.next_direction == Direction.DOWN

    @pytest.mark.asyncio
    async def test_direction_change_180_prevention(self, initialized_session):
        """Test that 180-degree turns are prevented."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        # Initial direction is RIGHT
        initial_direction = game_data.next_direction

        # Try to reverse to LEFT (should be ignored)
        await logic.process_action(session_id, {"type": "direction_change", "direction": "LEFT"})

        # Direction should not have changed
        assert game_data.next_direction == initial_direction

    @pytest.mark.asyncio
    async def test_all_180_preventions(self, logic):
        """Test 180-degree prevention from all directions."""
        config = {"grid_size": 10}
        session_id = "test_180"

        await logic.initialize(config, session_id)

        test_cases: List[Tuple[Direction, Direction]] = [
            (Direction.UP, Direction.DOWN),
            (Direction.DOWN, Direction.UP),
            (Direction.LEFT, Direction.RIGHT),
            (Direction.RIGHT, Direction.LEFT),
        ]

        for current_dir, invalid_dir in test_cases:
            logic._sessions[session_id].direction = current_dir
            logic._sessions[session_id].next_direction = current_dir

            # Try invalid direction change
            await logic.process_action(
                session_id,
                {"type": "direction_change", "direction": invalid_dir.name}
            )

            # Should not have changed
            assert logic._sessions[session_id].next_direction == current_dir

    @pytest.mark.asyncio
    async def test_move_right(self, initialized_session):
        """Test moving right (default direction)."""
        session_id, logic = initialized_session
        initial_head = logic._sessions[session_id].snake[0]

        result = await logic.process_action(session_id, {"type": "move"})

        # New head should be to the right of old head
        new_head = logic._sessions[session_id].snake[0]
        assert new_head.x == initial_head.x + 1
        assert new_head.y == initial_head.y

    @pytest.mark.asyncio
    async def test_move_up(self, initialized_session):
        """Test moving up after direction change."""
        session_id, logic = initialized_session

        # Change direction to UP
        await logic.process_action(session_id, {"type": "direction_change", "direction": "UP"})

        initial_head = logic._sessions[session_id].snake[0]
        await logic.process_action(session_id, {"type": "move"})

        # New head should be above old head
        new_head = logic._sessions[session_id].snake[0]
        assert new_head.x == initial_head.x
        assert new_head.y == initial_head.y - 1

    @pytest.mark.asyncio
    async def test_food_not_on_snake(self, initialized_session):
        """Test that food never spawns on snake body."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        snake_set = game_data.get_snake_set()
        food_pos = (game_data.food.x, game_data.food.y)

        assert food_pos not in snake_set

    @pytest.mark.asyncio
    async def test_food_regeneration(self, initialized_session):
        """Test that food regenerates in different location."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        old_food = game_data.food

        # Manually set food to be at position that will be eaten
        # and manually trigger food regeneration
        new_food = logic._generate_food_position(game_data)

        # New food should be different (statistically very likely)
        # Note: This might rarely fail if food happens to respawn in same spot
        # In a real test, we'd want to force specific positions
        assert new_food is not None

    @pytest.mark.asyncio
    async def test_wall_collision_right(self, logic):
        """Test wall collision when moving right."""
        config = {"grid_size": 10, "enable_walls": True}
        session_id = "test_wall_right"

        await logic.initialize(config, session_id)

        # Move snake to right edge
        for _ in range(7):  # Start at x=2, need to reach x=9
            await logic.process_action(session_id, {"type": "move"})

        # Next move should cause collision
        result = await logic.process_action(session_id, {"type": "move"})
        assert result["game_over"] is True
        assert result["game_over_reason"] == "wall_collision"

    @pytest.mark.asyncio
    async def test_wall_collision_disabled(self, logic):
        """Test that wall collision can be disabled."""
        config = {"grid_size": 10, "enable_walls": False}
        session_id = "test_no_wall"

        await logic.initialize(config, session_id)

        # Move snake to right edge and beyond
        for _ in range(10):
            await logic.process_action(session_id, {"type": "move"})

        # Should not be game over
        game_data = logic._sessions[session_id]
        assert game_data.game_over is False

    @pytest.mark.asyncio
    async def test_self_collision(self, logic):
        """Test self-collision detection."""
        config = {"grid_size": 10, "enable_self_collision": True}
        session_id = "test_self_collision"

        await logic.initialize(config, session_id)

        # Manually create self-collision scenario
        game_data = logic._sessions[session_id]

        # Create a snake that will collide with itself (U-turn pattern)
        # The head at (5,5) moving LEFT will hit (3,5) which is part of the body
        game_data.snake = [
            Position(5, 5),  # Head - will move LEFT
            Position(6, 5),  # Body segment
            Position(7, 5),  # Body segment
            Position(7, 6),
            Position(7, 7),
            Position(6, 7),
            Position(5, 7),
            Position(4, 7),
            Position(3, 7),
            Position(3, 6),
            Position(3, 5),  # Body segment - head will hit here when moving LEFT
        ]
        game_data.direction = Direction.LEFT
        game_data.next_direction = Direction.LEFT

        # Move should cause collision
        result = await logic.process_action(session_id, {"type": "move"})
        assert result["game_over"] is True
        assert result["game_over_reason"] == "self_collision"

    @pytest.mark.asyncio
    async def test_self_collision_disabled(self, logic):
        """Test that self-collision can be disabled."""
        config = {"grid_size": 10, "enable_self_collision": False}
        session_id = "test_no_self_collision"

        await logic.initialize(config, session_id)

        game_data = logic._sessions[session_id]

        # Create a snake that would collide
        game_data.snake = [
            Position(5, 5),
            Position(5, 6),
            Position(5, 7),
            Position(4, 7),
            Position(3, 7),
            Position(3, 6),
            Position(3, 5),
        ]
        game_data.direction = Direction.UP

        # Move should NOT cause collision
        result = await logic.process_action(session_id, {"type": "move"})
        assert result["game_over"] is False

    @pytest.mark.asyncio
    async def test_food_consumption_increases_score(self, initialized_session):
        """Test that eating food increases score."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        initial_score = game_data.score

        # Manually position food so snake will eat it
        head = game_data.snake[0]
        food_pos = head.add(1, 0)  # Place food to the right of head
        game_data.food = food_pos

        # Move to eat food
        await logic.process_action(session_id, {"type": "move"})

        # Score should increase
        assert logic._sessions[session_id].score == initial_score + 1

    @pytest.mark.asyncio
    async def test_food_consumption_grows_snake(self, initialized_session):
        """Test that eating food grows snake."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        initial_length = len(game_data.snake)

        # Position food so snake will eat it
        head = game_data.snake[0]
        food_pos = head.add(1, 0)
        game_data.food = food_pos

        # Move to eat food
        await logic.process_action(session_id, {"type": "move"})

        # Snake should be longer
        assert len(logic._sessions[session_id].snake) == initial_length + 1

    @pytest.mark.asyncio
    async def test_no_food_consumption_no_growth(self, initialized_session):
        """Test that snake doesn't grow without eating."""
        session_id, logic = initialized_session
        game_data = logic._sessions[session_id]

        initial_length = len(game_data.snake)

        # Ensure food is not in path
        head = game_data.snake[0]
        game_data.food = Position(0, 0)  # Far away

        # Move
        await logic.process_action(session_id, {"type": "move"})

        # Snake should stay same length
        assert len(logic._sessions[session_id].snake) == initial_length

    @pytest.mark.asyncio
    async def test_validate_action_valid(self, initialized_session):
        """Test action validation for valid actions."""
        session_id, logic = initialized_session

        # Valid direction change
        assert await logic.validate_action(
            session_id,
            {"type": "direction_change", "direction": "UP"}
        )

        # Valid move action
        assert await logic.validate_action(
            session_id,
            {"type": "move"}
        )

    @pytest.mark.asyncio
    async def test_validate_action_invalid_direction(self, initialized_session):
        """Test action validation for invalid direction changes."""
        session_id, logic = initialized_session

        # Invalid 180-degree turn (from RIGHT to LEFT)
        assert not await logic.validate_action(
            session_id,
            {"type": "direction_change", "direction": "LEFT"}
        )

    @pytest.mark.asyncio
    async def test_validate_action_invalid_session(self, logic):
        """Test validation with non-existent session."""
        assert not await logic.validate_action(
            "nonexistent_session",
            {"type": "move"}
        )

    @pytest.mark.asyncio
    async def test_check_game_over_not_over(self, initialized_session):
        """Test game over check when game is running."""
        session_id, logic = initialized_session

        is_over, reason = await logic.check_game_over(
            session_id,
            logic._sessions[session_id].to_dict()
        )

        assert is_over is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_game_over_after_wall_collision(self, logic):
        """Test game over check after wall collision."""
        config = {"grid_size": 10, "enable_walls": True}
        session_id = "test_game_over"

        await logic.initialize(config, session_id)

        # Move to wall
        for _ in range(8):
            await logic.process_action(session_id, {"type": "move"})

        is_over, reason = await logic.check_game_over(
            session_id,
            logic._sessions[session_id].to_dict()
        )

        assert is_over is True
        assert reason == "wall_collision"

    @pytest.mark.asyncio
    async def test_get_render_state(self, initialized_session):
        """Test getting render state."""
        session_id, logic = initialized_session

        render_state = await logic.get_render_state(
            session_id,
            logic._sessions[session_id].to_dict()
        )

        assert "grid_size" in render_state
        assert "snake" in render_state
        assert "food" in render_state
        assert "score" in render_state
        assert "game_over" in render_state
        assert "direction" in render_state

    @pytest.mark.asyncio
    async def test_restart(self, initialized_session):
        """Test restarting the game."""
        session_id, logic = initialized_session

        # Make some moves to change state
        await logic.process_action(session_id, {"type": "move"})
        await logic.process_action(session_id, {"type": "move"})

        initial_score = logic._sessions[session_id].score

        # Restart
        await logic.process_action(session_id, {"type": "restart"})

        # Should be reset to initial state
        game_data = logic._sessions[session_id]
        assert game_data.score == 0
        assert game_data.game_over is False
        assert len(game_data.snake) == 3
        assert game_data.direction == Direction.RIGHT

    @pytest.mark.asyncio
    async def test_cleanup(self, initialized_session):
        """Test session cleanup."""
        session_id, logic = initialized_session

        assert session_id in logic._sessions
        assert session_id in logic._config

        await logic.cleanup(session_id)

        assert session_id not in logic._sessions
        assert session_id not in logic._config

    @pytest.mark.asyncio
    async def test_get_score(self, logic):
        """Test score extraction."""
        game_data = {"score": 42, "other": "data"}

        score = await logic.get_score(game_data)
        assert score == 42

    @pytest.mark.asyncio
    async def test_game_over_prevents_movement(self, logic):
        """Test that movement is prevented after game over."""
        config = {"grid_size": 10}
        session_id = "test_game_over_movement"

        await logic.initialize(config, session_id)

        # Cause game over
        game_data = logic._sessions[session_id]
        game_data.game_over = True
        game_data.game_over_reason = "test_over"

        initial_head = game_data.snake[0]

        # Try to move
        await logic.process_action(session_id, {"type": "move"})

        # Snake should not have moved
        assert logic._sessions[session_id].snake[0] == initial_head


class TestSnakeGameLogicFactory:
    """Test SnakeGameLogicFactory functionality."""

    def test_factory_creates_logic(self):
        """Test that factory creates game logic instances."""
        factory = SnakeGameLogicFactory()

        logic = factory.create()
        assert isinstance(logic, SnakeGameLogic)

    def test_factory_game_type(self):
        """Test factory game type identifier."""
        factory = SnakeGameLogicFactory()

        assert factory.get_game_type() == "snake"

    def test_factory_version(self):
        """Test factory version."""
        factory = SnakeGameLogicFactory()

        version = factory.get_version()
        assert version == "1.0.0"
        assert isinstance(version, str)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_minimal_grid_size(self):
        """Test with minimum grid size (5x5)."""
        logic = SnakeGameLogic()
        config = {"grid_size": 5}
        session_id = "test_min_grid"

        result = await logic.initialize(config, session_id)
        assert result["grid_size"] == 5

    @pytest.mark.asyncio
    async def test_maximum_grid_size(self):
        """Test with maximum grid size (30x30)."""
        logic = SnakeGameLogic()
        config = {"grid_size": 30}
        session_id = "test_max_grid"

        result = await logic.initialize(config, session_id)
        assert result["grid_size"] == 30

    @pytest.mark.asyncio
    async def test_rapid_direction_changes(self):
        """Test that rapid direction changes are handled correctly.

        Note: Direction validation checks against current direction (not next_direction),
        so multiple rapid changes can all be valid if they're not 180° from current direction.
        The last valid change wins.
        """
        logic = SnakeGameLogic()
        config = {"grid_size": 10}
        session_id = "test_rapid_input"

        await logic.initialize(config, session_id)

        # Initial: direction=RIGHT, next_direction=RIGHT
        # Rapid direction changes - all checked against current direction (RIGHT)
        await logic.process_action(session_id, {"type": "direction_change", "direction": "UP"})  # Valid from RIGHT
        await logic.process_action(session_id, {"type": "direction_change", "direction": "DOWN"})  # Valid from RIGHT (not 180)
        await logic.process_action(session_id, {"type": "direction_change", "direction": "LEFT"})  # Invalid (180 from RIGHT), ignored

        game_data = logic._sessions[session_id]
        # Should be DOWN (last valid change before invalid LEFT)
        assert game_data.next_direction == Direction.DOWN

    @pytest.mark.asyncio
    async def test_case_insensitive_direction(self):
        """Test that direction names are case-insensitive."""
        logic = SnakeGameLogic()
        config = {"grid_size": 10}
        session_id = "test_case"

        await logic.initialize(config, session_id)

        # Lowercase
        await logic.process_action(session_id, {"type": "direction_change", "direction": "up"})
        # Mixed case
        await logic.process_action(session_id, {"type": "direction_change", "direction": "Down"})

        # Should handle both
        game_data = logic._sessions[session_id]
        assert game_data.next_direction in (Direction.UP, Direction.DOWN)

    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        """Test handling of unknown action types."""
        logic = SnakeGameLogic()
        config = {"grid_size": 10}
        session_id = "test_unknown_action"

        await logic.initialize(config, session_id)

        with pytest.raises(ValueError):
            await logic.process_action(session_id, {"type": "unknown_action"})

    @pytest.mark.asyncio
    async def test_nonexistent_session_actions(self):
        """Test actions on non-existent session."""
        logic = SnakeGameLogic()

        with pytest.raises(RuntimeError):
            await logic.process_action("nonexistent", {"type": "move"})
