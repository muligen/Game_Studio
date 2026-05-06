/**
 * Pure game logic functions for Snake game
 * Separated from UI for testability
 */

import { Position, Direction, GameConfig } from './types';

/**
 * Initialize snake at starting position
 */
export function createInitialSnake(): Position[] {
  return [
    { x: 5, y: 10 },
    { x: 4, y: 10 },
    { x: 3, y: 10 }
  ];
}

/**
 * Create initial direction (moving right)
 */
export function createInitialDirection(): Direction {
  return { x: 1, y: 0 };
}

/**
 * Check if position is on snake body
 */
export function isOnSnake(snake: Position[], x: number, y: number): boolean {
  return snake.some(segment => segment.x === x && segment.y === y);
}

/**
 * Generate food at random position not on snake
 */
export function generateFood(snake: Position[], gridSize: number): Position {
  const maxAttempts = 100;
  let attempts = 0;

  // Try random positions
  while (attempts < maxAttempts) {
    const food = {
      x: Math.floor(Math.random() * gridSize),
      y: Math.floor(Math.random() * gridSize)
    };

    if (!isOnSnake(snake, food.x, food.y)) {
      return food;
    }

    attempts++;
  }

  // Fallback: find first empty position
  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      if (!isOnSnake(snake, x, y)) {
        return { x, y };
      }
    }
  }

  // Should never reach here if there's space
  return { x: 0, y: 0 };
}

/**
 * Calculate new head position based on current position and direction
 */
export function calculateNewHead(head: Position, direction: Direction): Position {
  return {
    x: head.x + direction.x,
    y: head.y + direction.y
  };
}

/**
 * Check wall collision
 */
export function checkWallCollision(position: Position, gridSize: number): boolean {
  return position.x < 0 || position.x >= gridSize || position.y < 0 || position.y >= gridSize;
}

/**
 * Check self collision
 */
export function checkSelfCollision(position: Position, snake: Position[]): boolean {
  return isOnSnake(snake, position.x, position.y);
}

/**
 * Check if direction change is valid (no 180-degree turns)
 */
export function isValidDirectionChange(current: Direction, next: Direction): boolean {
  // Can't reverse direction (180-degree turn)
  return !(current.x + next.x === 0 && current.y + next.y === 0);
}

/**
 * Update snake position based on direction and food
 */
export function updateSnake(
  snake: Position[],
  direction: Direction,
  food: Position,
  gridSize: number,
  foodScore: number
): { snake: Position[]; ateFood: boolean; gameOver: boolean; scoreIncrement: number } {
  const newHead = calculateNewHead(snake[0], direction);

  // Check collisions
  if (checkWallCollision(newHead, gridSize) || checkSelfCollision(newHead, snake)) {
    return { snake, ateFood: false, gameOver: true, scoreIncrement: 0 };
  }

  // Add new head
  const newSnake = [newHead, ...snake];

  // Check if ate food
  if (newHead.x === food.x && newHead.y === food.y) {
    return { snake: newSnake, ateFood: true, gameOver: false, scoreIncrement: foodScore };
  }

  // Remove tail if didn't eat
  newSnake.pop();
  return { snake: newSnake, ateFood: false, gameOver: false, scoreIncrement: 0 };
}

/**
 * Get key code from keyboard event
 */
export function getKeyCode(e: KeyboardEvent): string {
  return e.code;
}

/**
 * Check if key is a pause/resume key
 */
export function isPauseKey(keyCode: string): boolean {
  return keyCode === 'Escape' || keyCode === 'KeyP';
}

/**
 * Check if key is a direction control
 */
export function isDirectionKey(keyCode: string): boolean {
  return ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyA', 'KeyS', 'KeyD'].includes(keyCode);
}

/**
 * Get direction from key code
 */
export function getDirectionFromKey(keyCode: string): Direction | null {
  switch (keyCode) {
    case 'ArrowUp':
    case 'KeyW':
      return { x: 0, y: -1 };
    case 'ArrowDown':
    case 'KeyS':
      return { x: 0, y: 1 };
    case 'ArrowLeft':
    case 'KeyA':
      return { x: -1, y: 0 };
    case 'ArrowRight':
    case 'KeyD':
      return { x: 1, y: 0 };
    default:
      return null;
  }
}

/**
 * Calculate new game speed based on current speed and configuration
 */
export function calculateNewSpeed(currentSpeed: number, config: GameConfig): number {
  return Math.max(config.minSpeed, currentSpeed - config.speedIncrement);
}

/**
 * Load high score from localStorage
 */
export function loadHighScore(): number {
  try {
    const saved = localStorage.getItem('snakeHighScore');
    return saved !== null ? parseInt(saved, 10) : 0;
  } catch (e) {
    console.warn('localStorage not available:', e);
    return 0;
  }
}

/**
 * Save high score to localStorage
 */
export function saveHighScore(score: number, currentHighScore: number): boolean {
  try {
    if (score > currentHighScore) {
      localStorage.setItem('snakeHighScore', score.toString());
      return true;
    }
  } catch (e) {
    console.warn('Failed to save high score:', e);
  }
  return false;
}
