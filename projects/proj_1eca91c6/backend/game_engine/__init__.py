"""
Game Studio Game Engine Module

A generic, extensible framework for building browser-based games
with support for multiple game types through a plugin architecture.
"""

__version__ = "1.0.0"

from game_engine.interfaces.game_state import GameState, GameSession, IGameStateManager
from game_engine.interfaces.game_logic import IGameLogic
from game_engine.core.game_engine import GameEngine
from game_engine.core.state_manager import InMemoryStateManager
from game_engine.config.config_manager import ConfigManager, GameConfigSchema

__all__ = [
    "GameState",
    "GameSession",
    "IGameStateManager",
    "IGameLogic",
    "GameEngine",
    "InMemoryStateManager",
    "ConfigManager",
    "GameConfigSchema",
]
