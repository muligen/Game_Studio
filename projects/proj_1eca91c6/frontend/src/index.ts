/**
 * Snake Game UI - Main Entry Point
 *
 * Export all game UI components for external use
 */

export { GameCanvas } from './components/GameCanvas';
export { ScoreDisplay } from './components/ScoreDisplay';
export { GameControls } from './components/GameControls';
export { GameOverScreen } from './components/GameOverScreen';
export { SnakeGame } from './components/SnakeGame';
export { useSnakeGame } from './hooks/useSnakeGame';

export type {
  GameCanvasProps,
  Position,
  SnakeSegment,
  FoodItem,
  GameState as GameStateType,
} from './types/game.types';

export { GameState } from './types/game.types';
