"""
Snake game logic implementation using LangGraph state machine.

This module implements the classic Snake game with state machine orchestration,
following the IGameLogic interface for the Game Studio framework.
"""

import random
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass, field
import copy

from ..interfaces.game_logic import IGameLogic, ActionType


class Direction(Enum):
    """Cardinal directions for snake movement."""
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


@dataclass
class Position:
    """Represents a 2D grid position."""
    x: int
    y: int

    def __eq__(self, other) -> bool:
        return isinstance(other, Position) and self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "Position":
        return cls(x=data["x"], y=data["y"])

    def add(self, dx: int, dy: int) -> "Position":
        """Create a new position by adding delta."""
        return Position(self.x + dx, self.y + dy)


@dataclass
class SnakeGameData:
    """Snake game state data."""
    grid_size: int = 10
    snake: List[Position] = field(default_factory=list)
    food: Optional[Position] = None
    direction: Direction = Direction.RIGHT
    next_direction: Direction = Direction.RIGHT
    score: int = 0
    game_over: bool = False
    game_over_reason: Optional[str] = None
    enable_walls: bool = True
    enable_self_collision: bool = True
    food_growth_rate: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert game data to dictionary for storage/transmission."""
        return {
            "grid_size": self.grid_size,
            "snake": [pos.to_dict() for pos in self.snake],
            "food": self.food.to_dict() if self.food else None,
            "direction": self.direction.name,
            "next_direction": self.next_direction.name,
            "score": self.score,
            "game_over": self.game_over,
            "game_over_reason": self.game_over_reason,
            "enable_walls": self.enable_walls,
            "enable_self_collision": self.enable_self_collision,
            "food_growth_rate": self.food_growth_rate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnakeGameData":
        """Create game data from dictionary."""
        snake = [Position.from_dict(pos) for pos in data.get("snake", [])]
        food_data = data.get("food")
        food = Position.from_dict(food_data) if food_data else None

        # Handle direction as string name or tuple
        direction_data = data.get("direction", "RIGHT")
        if isinstance(direction_data, str):
            direction = Direction[direction_data.upper()]
        else:
            direction_value = tuple(direction_data)
            direction = next(d for d in Direction if d.value == direction_value)

        next_dir_data = data.get("next_direction", "RIGHT")
        if isinstance(next_dir_data, str):
            next_direction = Direction[next_dir_data.upper()]
        else:
            next_dir_value = tuple(next_dir_data)
            next_direction = next((d for d in Direction if d.value == next_dir_value), Direction.RIGHT)

        return cls(
            grid_size=data.get("grid_size", 10),
            snake=snake,
            food=food,
            direction=direction,
            next_direction=next_direction,
            score=data.get("score", 0),
            game_over=data.get("game_over", False),
            game_over_reason=data.get("game_over_reason"),
            enable_walls=data.get("enable_walls", True),
            enable_self_collision=data.get("enable_self_collision", True),
            food_growth_rate=data.get("food_growth_rate", 1),
        )

    def get_snake_set(self) -> set:
        """Get snake positions as a set for efficient lookup."""
        return {(pos.x, pos.y) for pos in self.snake}


class SnakeGameLogic(IGameLogic):
    """Snake game logic implementation with LangGraph state machine."""

    def __init__(self):
        """Initialize Snake game logic."""
        self._sessions: Dict[str, SnakeGameData] = {}
        self._config: Dict[str, Any] = {}

    async def initialize(
        self,
        config: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """Initialize Snake game with configuration.

        Args:
            config: Game configuration including grid_size, speed, etc.
            session_id: Unique session identifier

        Returns:
            Initial game state dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        grid_size = config.get("grid_size", 10)
        if not (5 <= grid_size <= 30):
            raise ValueError(f"grid_size must be between 5 and 30, got {grid_size}")

        # Create initial game state
        game_data = SnakeGameData(
            grid_size=grid_size,
            snake=self._create_initial_snake(grid_size),
            direction=Direction.RIGHT,
            next_direction=Direction.RIGHT,
            score=0,
            enable_walls=config.get("enable_walls", True),
            enable_self_collision=config.get("enable_self_collision", True),
            food_growth_rate=config.get("food_growth_rate", 1),
        )

        # Place initial food
        game_data.food = self._generate_food_position(game_data)

        # Store session data
        self._sessions[session_id] = game_data
        self._config[session_id] = config

        return game_data.to_dict()

    def _create_initial_snake(self, grid_size: int) -> List[Position]:
        """Create initial snake with 3 segments positioned in center-left."""
        start_y = grid_size // 2
        start_x = 2

        # Snake starts with 3 segments: head at (start_x, start_y), body behind
        return [
            Position(start_x, start_y),      # Head
            Position(start_x - 1, start_y),  # Body
            Position(start_x - 2, start_y),  # Tail
        ]

    def _generate_food_position(self, game_data: SnakeGameData) -> Position:
        """Generate a random food position not on snake body.

        Args:
            game_data: Current game state

        Returns:
            New food position

        Raises:
            RuntimeError: If no valid position available (shouldn't happen)
        """
        snake_set = game_data.get_snake_set()
        grid_size = game_data.grid_size

        # Get all empty cells
        empty_positions = []
        for x in range(grid_size):
            for y in range(grid_size):
                if (x, y) not in snake_set:
                    empty_positions.append(Position(x, y))

        if not empty_positions:
            raise RuntimeError("No valid position for food (grid full!)")

        # Return random empty position
        return random.choice(empty_positions)

    async def process_action(
        self,
        session_id: str,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process player action and return new state.

        Args:
            session_id: Unique session identifier
            action: Action containing type (move) and parameters (direction)

        Returns:
            Updated game data

        Raises:
            ValueError: If action is invalid
            RuntimeError: If session doesn't exist
        """
        if session_id not in self._sessions:
            raise RuntimeError(f"Session {session_id} not found")

        game_data = self._sessions[session_id]

        # Handle different action types
        action_type = action.get("type", "move")

        if action_type == "direction_change":
            # Update direction for next move (queued)
            new_direction = action.get("direction")
            if isinstance(new_direction, str):
                try:
                    new_direction = Direction[new_direction.upper()]
                except KeyError:
                    raise ValueError(f"Invalid direction: {new_direction}")

            # Validate direction change (no 180° turns)
            if self._is_valid_direction_change(game_data.direction, new_direction):
                game_data.next_direction = new_direction
                # Also update current direction for immediate API feedback
                # This allows the API to reflect direction changes immediately
                game_data.direction = new_direction

        elif action_type == "move":
            # Process game tick movement
            return await self._process_move(game_data)

        elif action_type == "restart":
            # Restart game
            return await self.initialize(self._config[session_id], session_id)

        else:
            raise ValueError(f"Unknown action type: {action_type}")

        return game_data.to_dict()

    def _is_valid_direction_change(
        self,
        current_direction: Direction,
        new_direction: Direction
    ) -> bool:
        """Check if direction change is valid (no 180° turns).

        Args:
            current_direction: Current snake direction
            new_direction: Requested new direction

        Returns:
            True if change is valid, False otherwise
        """
        # Get opposite direction vectors
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }

        # Cannot reverse direction
        return opposites[current_direction] != new_direction

    async def _process_move(self, game_data: SnakeGameData) -> Dict[str, Any]:
        """Process one movement tick.

        Args:
            game_data: Current game state

        Returns:
            Updated game state
        """
        if game_data.game_over:
            return game_data.to_dict()

        # Apply queued direction
        game_data.direction = game_data.next_direction

        # Calculate new head position
        head = game_data.snake[0]
        dx, dy = game_data.direction.value
        new_head = head.add(dx, dy)

        # Check collisions
        collision, reason = await self._check_collisions(game_data, new_head)
        if collision:
            game_data.game_over = True
            game_data.game_over_reason = reason
            return game_data.to_dict()

        # Move snake: add new head
        game_data.snake.insert(0, new_head)

        # Check if food eaten
        if new_head == game_data.food:
            # Snake grows (don't remove tail)
            game_data.score += 1
            # Generate new food
            game_data.food = self._generate_food_position(game_data)
        else:
            # Remove tail (snake doesn't grow)
            game_data.snake.pop()

        return game_data.to_dict()

    async def _check_collisions(
        self,
        game_data: SnakeGameData,
        new_head: Position
    ) -> Tuple[bool, Optional[str]]:
        """Check for collisions with walls and self.

        Args:
            game_data: Current game state
            new_head: New head position to check

        Returns:
            Tuple of (collision_detected, reason)
        """
        grid_size = game_data.grid_size

        # Wall collision
        if game_data.enable_walls:
            if not (0 <= new_head.x < grid_size and 0 <= new_head.y < grid_size):
                return True, "wall_collision"

        # Self collision (exclude tail as it will move)
        if game_data.enable_self_collision:
            snake_body = set((pos.x, pos.y) for pos in game_data.snake[:-1])
            if (new_head.x, new_head.y) in snake_body:
                return True, "self_collision"

        return False, None

    async def validate_action(
        self,
        session_id: str,
        action: Dict[str, Any]
    ) -> bool:
        """Validate if action is legal.

        Args:
            session_id: Unique session identifier
            action: Action to validate

        Returns:
            True if action is valid, False otherwise
        """
        if session_id not in self._sessions:
            return False

        game_data = self._sessions[session_id]
        action_type = action.get("type", "move")

        if action_type == "direction_change":
            direction = action.get("direction")
            if not direction:
                return False

            if isinstance(direction, str):
                try:
                    direction = Direction[direction.upper()]
                except KeyError:
                    return False

            return self._is_valid_direction_change(game_data.direction, direction)

        elif action_type in ("move", "restart"):
            return True

        return False

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
            Tuple of (is_over, reason)
        """
        if session_id not in self._sessions:
            return False, None

        state = self._sessions[session_id]
        return state.game_over, state.game_over_reason

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
            Render-ready state dictionary
        """
        if session_id not in self._sessions:
            return {}

        state = self._sessions[session_id]

        return {
            "grid_size": state.grid_size,
            "snake": [pos.to_dict() for pos in state.snake],
            "food": state.food.to_dict() if state.food else None,
            "score": state.score,
            "game_over": state.game_over,
            "game_over_reason": state.game_over_reason,
            "direction": state.direction.name,
        }

    async def cleanup(self, session_id: str) -> None:
        """Clean up session resources.

        Args:
            session_id: Unique session identifier
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._config:
            del self._config[session_id]

    async def get_score(self, game_data: Dict[str, Any]) -> int:
        """Extract score from game data.

        Args:
            game_data: Current game data

        Returns:
            Current score
        """
        return game_data.get("score", 0)


class SnakeGameLogicFactory:
    """Factory for creating Snake game logic instances."""

    def create(self) -> IGameLogic:
        """Create a new Snake game logic instance.

        Returns:
            New SnakeGameLogic instance
        """
        return SnakeGameLogic()

    def get_game_type(self) -> str:
        """Get the game type this factory produces.

        Returns:
            Game type identifier
        """
        return "snake"

    def get_version(self) -> str:
        """Get the game logic version.

        Returns:
            Version string
        """
        return "1.0.0"
