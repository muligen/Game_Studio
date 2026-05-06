/**
 * Game state types for Snake game
 */

export enum GameState {
  Menu = 'Menu',
  Playing = 'Playing',
  Paused = 'Paused',
  GameOver = 'GameOver'
}

export interface Position {
  x: number;
  y: number;
}

export interface Direction {
  x: number;
  y: number;
}

export interface GameLogicState {
  snake: Position[];
  food: Position;
  direction: Direction;
  nextDirection: Direction;
  score: number;
  highScore: number;
  gameSpeed: number;
}

export interface GameUIState {
  gameState: GameState;
  isNewHighScore: boolean;
  fps: number;
}

export interface GameStateProps extends GameLogicState, GameUIState {}

export type GameAction =
  | { type: 'START_GAME' }
  | { type: 'RESTART_GAME' }
  | { type: 'PAUSE_GAME' }
  | { type: 'RESUME_GAME' }
  | { type: 'CHANGE_DIRECTION'; payload: Direction }
  | { type: 'UPDATE_SNAKE'; payload: { snake: Position[]; food: Position; score: number; gameSpeed?: number } }
  | { type: 'GAME_OVER'; payload: { isNewHighScore: boolean } }
  | { type: 'UPDATE_FPS'; payload: number }
  | { type: 'LOAD_HIGH_SCORE'; payload: number };

export interface GameConfig {
  gridSize: number;
  initialSpeed: number;
  speedIncrement: number;
  minSpeed: number;
  foodScore: number;
  canvasSize: number;
}

export const DEFAULT_GAME_CONFIG: GameConfig = {
  gridSize: 20,
  initialSpeed: 150,
  speedIncrement: 2,
  minSpeed: 50,
  foodScore: 10,
  canvasSize: 600
};
