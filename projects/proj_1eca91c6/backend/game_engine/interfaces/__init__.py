"""Game engine interface definitions."""

from .game_state import GameState, GameSession, IGameStateManager
from .game_logic import IGameLogic

__all__ = [
    "GameState",
    "GameSession",
    "IGameStateManager",
    "IGameLogic",
]
