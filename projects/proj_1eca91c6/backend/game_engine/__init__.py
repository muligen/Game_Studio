"""
Game Studio Game Engine Module

A generic, extensible framework for building browser-based games
with support for multiple game types through a plugin architecture.
"""

__version__ = "1.0.0"

from .interfaces.game_state import GameState, GameSession, IGameStateManager
from .interfaces.game_logic import IGameLogic
from .core.snake_logic import SnakeGameLogic, SnakeGameLogicFactory
from .core.snake_state_machine import SnakeGameStateMachine, SnakeStateMachineFactory

__all__ = [
    "GameState",
    "GameSession",
    "IGameStateManager",
    "IGameLogic",
    "SnakeGameLogic",
    "SnakeGameLogicFactory",
    "SnakeGameStateMachine",
    "SnakeStateMachineFactory",
]
