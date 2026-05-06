/**
 * SnakeGame Component
 *
 * Main game component that integrates all UI elements
 */

import React, { useEffect, useCallback, useRef } from 'react';
import { SnakeGameProps, GameState } from '../types/game.types';
import { useSnakeGame } from '../hooks/useSnakeGame';
import { GameCanvas } from './GameCanvas';
import { ScoreDisplay } from './ScoreDisplay';
import { GameControls } from './GameControls';
import { GameOverScreen } from './GameOverScreen';
import '../styles/SnakeGame.css';

export const SnakeGame: React.FC<SnakeGameProps> = ({
  config,
  onStateChange,
  onScoreChange,
  className = '',
}) => {
  const {
    gameState,
    gameData,
    startGame,
    pauseGame,
    resumeGame,
    restartGame,
    handleKeyPress,
  } = useSnakeGame({
    config,
    onStateChange,
    onScoreChange,
  });

  const gameContainerRef = useRef<HTMLDivElement>(null);

  // Handle keyboard input
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Only handle keyboard when game container has focus or mouse is over it
    if (!gameContainerRef.current?.contains(document.activeElement)) {
      return;
    }

    switch (event.key) {
      case 'ArrowUp':
      case 'w':
      case 'W':
        event.preventDefault();
        if (gameState === GameState.RUNNING) {
          handleKeyPress('UP');
        }
        break;
      case 'ArrowDown':
      case 's':
      case 'S':
        event.preventDefault();
        if (gameState === GameState.RUNNING) {
          handleKeyPress('DOWN');
        }
        break;
      case 'ArrowLeft':
      case 'a':
      case 'A':
        event.preventDefault();
        if (gameState === GameState.RUNNING) {
          handleKeyPress('LEFT');
        }
        break;
      case 'ArrowRight':
      case 'd':
      case 'D':
        event.preventDefault();
        if (gameState === GameState.RUNNING) {
          handleKeyPress('RIGHT');
        }
        break;
      case ' ':
        event.preventDefault();
        if (gameState === GameState.RUNNING) {
          pauseGame();
        } else if (gameState === GameState.PAUSED) {
          resumeGame();
        } else if (gameState === GameState.READY) {
          startGame();
        }
        break;
      case 'Enter':
      case 'r':
      case 'R':
        event.preventDefault();
        if (gameState === GameState.GAME_OVER || gameState === GameState.READY) {
          restartGame();
        }
        break;
    }
  }, [gameState, handleKeyPress, startGame, pauseGame, resumeGame, restartGame]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const isNewHighScore = gameData.score > 0 && gameData.score >= gameData.highScore;
  const showGameOver = gameState === GameState.GAME_OVER;

  const getGameStatusText = (): string => {
    switch (gameState) {
      case GameState.READY:
        return 'Press SPACE to start';
      case GameState.RUNNING:
        return 'Playing';
      case GameState.PAUSED:
        return 'Paused';
      case GameState.GAME_OVER:
        return 'Game Over';
      default:
        return '';
    }
  };

  return (
    <div
      ref={gameContainerRef}
      className={`snake-game ${className}`}
      tabIndex={-1}
      role="application"
      aria-label="Snake Game"
    >
      {/* Header */}
      <header className="game-header">
        <div className="game-title">
          <span role="img" aria-label="Snake emoji">🐍</span>
          <span>SNAKE</span>
        </div>

        <ScoreDisplay
          score={gameData.score}
          highScore={gameData.highScore}
        />

        <GameControls
          gameState={gameState}
          onPause={pauseGame}
          onResume={resumeGame}
          onRestart={restartGame}
        />
      </header>

      {/* Main Game Area */}
      <main className="game-main">
        <div className="game-canvas-container">
          <GameCanvas
            gameState={gameState}
            gameData={gameData}
          />

          {showGameOver && (
            <GameOverScreen
              score={gameData.score}
              highScore={gameData.highScore}
              onRestart={restartGame}
              isNewHighScore={isNewHighScore}
            />
          )}

          {/* Start prompt overlay */}
          {gameState === GameState.READY && (
            <div className="start-game-overlay">
              <p className="start-message">Press SPACE to Start</p>
              <button
                className="btn-primary start-button"
                onClick={startGame}
                aria-label="Start game"
              >
                START GAME
              </button>
            </div>
          )}

          {/* Paused overlay */}
          {gameState === GameState.PAUSED && (
            <div className="paused-overlay">
              <p className="paused-message">PAUSED</p>
              <p className="paused-hint">Press SPACE to resume</p>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="game-footer">
        <div className="game-status">
          <span
            className={`status-${gameState.toLowerCase()}`}
            aria-live="polite"
          >
            {getGameStatusText()}
          </span>
        </div>

        <div className="controls-help">
          <span className="help-label">Controls:</span>
          <div className="arrow-icons">
            <kbd>↑</kbd>
            <kbd>↓</kbd>
            <kbd>←</kbd>
            <kbd>→</kbd>
          </div>
          <span className="keyboard-shortcuts">Space: Pause | Enter: Restart</span>
        </div>
      </footer>
    </div>
  );
};
