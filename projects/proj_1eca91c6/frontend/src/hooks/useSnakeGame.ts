/**
 * useSnakeGame Hook
 *
 * Custom hook for managing snake game state and logic
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { GameState, GameData, GameConfig, Position } from '../types/game.types';

const DEFAULT_CONFIG: GameConfig = {
  gridSize: 10,
  initialSpeed: 500,
  enableWalls: true,
  enableSelfCollision: true,
  foodGrowthRate: 1,
  maxScore: undefined,
};

interface UseSnakeGameOptions {
  config?: Partial<GameConfig>;
  onStateChange?: (state: GameState) => void;
  onScoreChange?: (score: number) => void;
  onGameOver?: (finalScore: number) => void;
}

interface UseSnakeGameReturn {
  gameState: GameState;
  gameData: GameData;
  config: GameConfig;
  startGame: () => void;
  pauseGame: () => void;
  resumeGame: () => void;
  restartGame: () => void;
  handleKeyPress: (direction: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT') => void;
}

export const useSnakeGame = (options: UseSnakeGameOptions = {}): UseSnakeGameReturn => {
  const {
    config: userConfig = {},
    onStateChange,
    onScoreChange,
    onGameOver,
  } = options;

  const mergedConfig = { ...DEFAULT_CONFIG, ...userConfig };
  const [gameState, setGameState] = useState<GameState>(GameState.READY);
  const [score, setScore] = useState(0);
  const [highScore, setHighScore] = useState(0);
  const [snake, setSnake] = useState<Position[]>([{ x: 5, y: 5 }]);
  const [food, setFood] = useState<Position | null>(null);
  const [direction, setDirection] = useState<'UP' | 'DOWN' | 'LEFT' | 'RIGHT'>('RIGHT');
  const [nextDirection, setNextDirection] = useState<'UP' | 'DOWN' | 'LEFT' | 'RIGHT'>('RIGHT');

  const gameLoopRef = useRef<NodeJS.Timeout | null>(null);
  const previousScoreRef = useRef(0);

  // Generate random food position
  const generateFood = useCallback((currentSnake: Position[]): Position => {
    const gridSize = mergedConfig.gridSize;
    const snakePositions = new Set(currentSnake.map(s => `${s.x},${s.y}`));

    let newFood: Position;
    let attempts = 0;
    const maxAttempts = gridSize * gridSize;

    do {
      newFood = {
        x: Math.floor(Math.random() * gridSize),
        y: Math.floor(Math.random() * gridSize),
      };
      attempts++;
    } while (snakePositions.has(`${newFood.x},${newFood.y}`) && attempts < maxAttempts);

    return newFood;
  }, [mergedConfig.gridSize]);

  // Initialize food on mount
  useEffect(() => {
    if (!food && gameState === GameState.READY) {
      setFood(generateFood(snake));
    }
  }, [food, snake, gameState, generateFood]);

  // Check collision
  const checkCollision = useCallback((head: Position, body: Position[]): boolean => {
    // Wall collision
    if (mergedConfig.enableWalls) {
      if (
        head.x < 0 ||
        head.x >= mergedConfig.gridSize ||
        head.y < 0 ||
        head.y >= mergedConfig.gridSize
      ) {
        return true;
      }
    } else {
      // Wrap around
      if (head.x < 0) head.x = mergedConfig.gridSize - 1;
      if (head.x >= mergedConfig.gridSize) head.x = 0;
      if (head.y < 0) head.y = mergedConfig.gridSize - 1;
      if (head.y >= mergedConfig.gridSize) head.y = 0;
    }

    // Self collision
    if (mergedConfig.enableSelfCollision) {
      for (let i = 1; i < body.length; i++) {
        if (head.x === body[i].x && head.y === body[i].y) {
          return true;
        }
      }
    }

    return false;
  }, [mergedConfig]);

  // Game loop tick
  const gameTick = useCallback(() => {
    setSnake(currentSnake => {
      const head = currentSnake[0];
      const newHead = { ...head };

      switch (nextDirection) {
        case 'UP':
          newHead.y -= 1;
          break;
        case 'DOWN':
          newHead.y += 1;
          break;
        case 'LEFT':
          newHead.x -= 1;
          break;
        case 'RIGHT':
          newHead.x += 1;
          break;
      }

      // Check collision
      if (checkCollision(newHead, currentSnake)) {
        setGameState(GameState.GAME_OVER);
        if (onGameOver) {
          onGameOver(score);
        }
        return currentSnake;
      }

      const newSnake = [newHead, ...currentSnake];

      // Check food collision
      if (food && newHead.x === food.x && newHead.y === food.y) {
        const newScore = score + 1;
        setScore(newScore);
        setFood(generateFood(newSnake));
        if (onScoreChange) {
          onScoreChange(newScore);
        }
      } else {
        newSnake.pop();
      }

      setDirection(nextDirection);
      return newSnake;
    });
  }, [nextDirection, food, score, checkCollision, generateFood, onScoreChange, onGameOver]);

  // Start game loop
  useEffect(() => {
    if (gameState === GameState.RUNNING) {
      gameLoopRef.current = setTimeout(() => {
        gameTick();
      }, mergedConfig.initialSpeed);
    }

    return () => {
      if (gameLoopRef.current) {
        clearTimeout(gameLoopRef.current);
      }
    };
  }, [gameState, gameTick, mergedConfig.initialSpeed]);

  // Notify state changes
  useEffect(() => {
    if (onStateChange) {
      onStateChange(gameState);
    }
  }, [gameState, onStateChange]);

  // Update high score
  useEffect(() => {
    if (score > highScore) {
      setHighScore(score);
    }
  }, [score, highScore]);

  const startGame = useCallback(() => {
    setGameState(GameState.RUNNING);
  }, []);

  const pauseGame = useCallback(() => {
    setGameState(GameState.PAUSED);
  }, []);

  const resumeGame = useCallback(() => {
    setGameState(GameState.RUNNING);
  }, []);

  const restartGame = useCallback(() => {
    setSnake([{ x: 5, y: 5 }]);
    setFood(generateFood([{ x: 5, y: 5 }]));
    setScore(0);
    setDirection('RIGHT');
    setNextDirection('RIGHT');
    setGameState(GameState.READY);
  }, [generateFood]);

  const handleKeyPress = useCallback((newDirection: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT') => {
    // Prevent 180-degree turns
    const opposites: Record<string, 'UP' | 'DOWN' | 'LEFT' | 'RIGHT'> = {
      UP: 'DOWN',
      DOWN: 'UP',
      LEFT: 'RIGHT',
      RIGHT: 'LEFT',
    };

    if (opposites[newDirection] !== direction) {
      setNextDirection(newDirection);
    }
  }, [direction]);

  const gameData: GameData = {
    snake: snake.map((pos, index) => ({ ...pos, index })),
    food: food ? { ...food, id: `food-${food.x}-${food.y}` } : null,
    score,
    highScore,
    gridWidth: mergedConfig.gridSize,
    gridHeight: mergedConfig.gridSize,
  };

  return {
    gameState,
    gameData,
    config: mergedConfig,
    startGame,
    pauseGame,
    resumeGame,
    restartGame,
    handleKeyPress,
  };
};
