/**
 * Game Type Definitions
 *
 * Core types for the Snake Game UI components
 */

/**
 * Generic game state enum
 */
export enum GameState {
  IDLE = 'idle',
  READY = 'ready',
  RUNNING = 'running',
  PAUSED = 'paused',
  GAME_OVER = 'game_over',
  ERROR = 'error',
}

/**
 * Position on the game grid
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * Snake segment with position and index
 */
export interface SnakeSegment extends Position {
  index: number;
}

/**
 * Food item with position
 */
export interface FoodItem extends Position {
  id: string;
}

/**
 * Game data from backend
 */
export interface GameData {
  snake: SnakeSegment[];
  food: FoodItem | null;
  score: number;
  highScore: number;
  gridWidth: number;
  gridHeight: number;
}

/**
 * Game configuration
 */
export interface GameConfig {
  gridSize: number;
  initialSpeed: number;
  enableWalls: boolean;
  enableSelfCollision: boolean;
  foodGrowthRate: number;
  maxScore?: number;
}

/**
 * Game canvas props
 */
export interface GameCanvasProps {
  gameState: GameState;
  gameData: GameData;
  cellSize?: number;
  className?: string;
  onRender?: (context: CanvasRenderingContext2D) => void;
}

/**
 * Score display props
 */
export interface ScoreDisplayProps {
  score: number;
  highScore: number;
  className?: string;
  showAnimation?: boolean;
}

/**
 * Game controls props
 */
export interface GameControlsProps {
  gameState: GameState;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Game over screen props
 */
export interface GameOverScreenProps {
  score: number;
  highScore: number;
  onRestart: () => void;
  isNewHighScore?: boolean;
  className?: string;
}

/**
 * Snake game main component props
 */
export interface SnakeGameProps {
  config?: Partial<GameConfig>;
  onStateChange?: (state: GameState) => void;
  onScoreChange?: (score: number) => void;
  className?: string;
}
