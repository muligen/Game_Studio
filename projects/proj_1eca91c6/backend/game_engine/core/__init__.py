"""
Core game logic implementations.

This module contains concrete implementations of game logic
for different game types in the Game Studio framework.
"""

from .snake_logic import (
    Direction,
    Position,
    SnakeGameData,
    SnakeGameLogic,
    SnakeGameLogicFactory,
)
from .snake_state_machine import (
    SnakeGameStateMachine,
    SnakeStateMachineFactory,
    SnakeStateMachineState,
)

__all__ = [
    # Snake game logic
    "Direction",
    "Position",
    "SnakeGameData",
    "SnakeGameLogic",
    "SnakeGameLogicFactory",
    # Snake state machine
    "SnakeGameStateMachine",
    "SnakeStateMachineFactory",
    "SnakeStateMachineState",
]
