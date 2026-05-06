/**
 * GameContainer Component
 * Main game container with state management using useReducer
 * Handles keyboard events and game loop
 */

import React, { useReducer, useEffect, useRef, useCallback, useState } from 'react';
import { GameState, GameAction, GameStateProps, DEFAULT_GAME_CONFIG } from './types';
import {
  createInitialSnake,
  createInitialDirection,
  generateFood,
  updateSnake,
  isValidDirectionChange,
  isPauseKey,
  isDirectionKey,
  getDirectionFromKey,
  calculateNewSpeed,
  loadHighScore,
  saveHighScore
} from './gameLogic';
import { GameCanvas } from './GameCanvas';
import { GameUI, HUD } from './GameUI';
import './Game.css';

interface GameContainerProps {
  config?: typeof DEFAULT_GAME_CONFIG;
}

const initialState: GameStateProps = {
  // Game logic state
  snake: createInitialSnake(),
  food: { x: 0, y: 0 },
  direction: createInitialDirection(),
  nextDirection: createInitialDirection(),
  score: 0,
  highScore: 0,
  gameSpeed: DEFAULT_GAME_CONFIG.initialSpeed,

  // UI state
  gameState: GameState.Menu,
  isNewHighScore: false,
  fps: 60
};

function gameReducer(state: GameStateProps, action: GameAction): GameStateProps {
  switch (action.type) {
    case 'START_GAME':
      const initialSnake = createInitialSnake();
      const initialDir = createInitialDirection();
      return {
        ...state,
        gameState: GameState.Playing,
        snake: initialSnake,
        food: generateFood(initialSnake, DEFAULT_GAME_CONFIG.gridSize),
        direction: initialDir,
        nextDirection: initialDir,
        score: 0,
        gameSpeed: DEFAULT_GAME_CONFIG.initialSpeed,
        isNewHighScore: false
      };

    case 'RESTART_GAME':
      return {
        ...state,
        gameState: GameState.Playing,
        snake: createInitialSnake(),
        food: generateFood(createInitialSnake(), DEFAULT_GAME_CONFIG.gridSize),
        direction: createInitialDirection(),
        nextDirection: createInitialDirection(),
        score: 0,
        gameSpeed: DEFAULT_GAME_CONFIG.initialSpeed,
        isNewHighScore: false
      };

    case 'PAUSE_GAME':
      return {
        ...state,
        gameState: GameState.Paused
      };

    case 'RESUME_GAME':
      return {
        ...state,
        gameState: GameState.Playing
      };

    case 'CHANGE_DIRECTION':
      if (isValidDirectionChange(state.direction, action.payload)) {
        return {
          ...state,
          nextDirection: action.payload
        };
      }
      return state;

    case 'UPDATE_SNAKE':
      return {
        ...state,
        snake: action.payload.snake,
        food: action.payload.food,
        direction: state.nextDirection,
        score: action.payload.score,
        gameSpeed: action.payload.gameSpeed ?? state.gameSpeed
      };

    case 'GAME_OVER':
      return {
        ...state,
        gameState: GameState.GameOver,
        isNewHighScore: action.payload.isNewHighScore
      };

    case 'UPDATE_FPS':
      return {
        ...state,
        fps: action.payload
      };

    case 'LOAD_HIGH_SCORE':
      return {
        ...state,
        highScore: action.payload
      };

    default:
      return state;
  }
}

export const GameContainer: React.FC<GameContainerProps> = ({
  config = DEFAULT_GAME_CONFIG
}) => {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const [canvasSize, setCanvasSize] = useState(600);

  const gameLoopRef = useRef<number>();
  const lastMoveTimeRef = useRef<number>(0);
  const lastFpsUpdateRef = useRef<number>(0);
  const frameCountRef = useRef<number>(0);

  // Load high score on mount
  useEffect(() => {
    const highScore = loadHighScore();
    dispatch({ type: 'LOAD_HIGH_SCORE', payload: highScore });
  }, []);

  // Handle keyboard input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const keyCode = e.code;

      // Prevent default for game keys
      if (isPauseKey(keyCode) || isDirectionKey(keyCode)) {
        e.preventDefault();
      }

      // Pause/Resume
      if (isPauseKey(keyCode)) {
        if (state.gameState === GameState.Playing) {
          dispatch({ type: 'PAUSE_GAME' });
        } else if (state.gameState === GameState.Paused) {
          dispatch({ type: 'RESUME_GAME' });
        }
        return;
      }

      // Direction controls (only when playing)
      if (state.gameState === GameState.Playing) {
        const direction = getDirectionFromKey(keyCode);
        if (direction) {
          dispatch({ type: 'CHANGE_DIRECTION', payload: direction });
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [state.gameState]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      const container = document.querySelector('.game-container');
      if (container) {
        const size = Math.min(container.clientWidth, container.clientHeight);
        setCanvasSize(size);
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Initial call

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Game loop
  useEffect(() => {
    if (state.gameState !== GameState.Playing && state.gameState !== GameState.Paused) {
      return;
    }

    const gameLoop = (currentTime: number) => {
      // Update FPS
      frameCountRef.current++;
      if (currentTime - lastFpsUpdateRef.current >= 1000) {
        const currentFps = frameCountRef.current;
        dispatch({ type: 'UPDATE_FPS', payload: currentFps });
        frameCountRef.current = 0;
        lastFpsUpdateRef.current = currentTime;

        // Log warning if FPS is too low (only in production)
        if (process.env.NODE_ENV === 'production' && currentFps < 30) {
          console.warn(`[Performance Monitor] Low FPS detected: ${currentFps}fps at ${new Date().toISOString()}`);
        }
      }

      // Update game logic based on speed
      if (state.gameState === GameState.Playing) {
        if (currentTime - lastMoveTimeRef.current >= state.gameSpeed) {
          lastMoveTimeRef.current = currentTime;

          const result = updateSnake(
            state.snake,
            state.nextDirection,
            state.food,
            config.gridSize,
            config.foodScore
          );

          if (result.gameOver) {
            const isNewHighScore = saveHighScore(state.score, state.highScore);
            dispatch({ type: 'GAME_OVER', payload: { isNewHighScore } });
          } else {
            const newScore = state.score + result.scoreIncrement;
            const newFood = result.ateFood
              ? generateFood(result.snake, config.gridSize)
              : state.food;

            dispatch({
              type: 'UPDATE_SNAKE',
              payload: {
                snake: result.snake,
                food: newFood,
                score: newScore,
                gameSpeed: result.ateFood ? calculateNewSpeed(state.gameSpeed, config) : undefined
              }
            });
          }
        }
      }

      gameLoopRef.current = requestAnimationFrame(gameLoop);
    };

    gameLoopRef.current = requestAnimationFrame(gameLoop);

    return () => {
      if (gameLoopRef.current) {
        cancelAnimationFrame(gameLoopRef.current);
      }
    };
  }, [state.gameState, state.snake, state.food, state.nextDirection, state.score, state.gameSpeed, state.highScore, config]);

  const handleStartGame = useCallback(() => {
    dispatch({ type: 'START_GAME' });
  }, []);

  const handleResumeGame = useCallback(() => {
    dispatch({ type: 'RESUME_GAME' });
  }, []);

  const handleRestartGame = useCallback(() => {
    dispatch({ type: 'RESTART_GAME' });
  }, []);

  return (
    <div className="game-wrapper">
      <div className="game-header">
        <h1>🐍 贪吃蛇</h1>
        <HUD score={state.score} highScore={state.highScore} />
      </div>

      <div className="game-container" role="application" aria-label="贪吃蛇游戏">
        <GameCanvas
          snake={state.snake}
          food={state.food}
          gameState={state.gameState}
          config={config}
          canvasSize={canvasSize}
        />

        <GameUI
          gameState={state.gameState}
          score={state.score}
          highScore={state.highScore}
          isNewHighScore={state.isNewHighScore}
          fps={state.fps}
          onStartGame={handleStartGame}
          onResumeGame={handleResumeGame}
          onRestartGame={handleRestartGame}
        />
      </div>

      <div className="controls-info">
        <p>
          控制: <kbd>↑</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> 或 <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> | 暂停: <kbd>Esc</kbd> 或 <kbd>P</kbd>
        </p>
      </div>
    </div>
  );
};
