"""Game engine interface definitions."""

from game_engine.interfaces.game_state import GameState, GameSession, IGameStateManager
from game_engine.interfaces.game_logic import IGameLogic

__all__ = [
    "GameState",
    "GameSession",
    "IGameStateManager",
    "IGameLogic",
]
