/**
 * GameControls Component
 *
 * Displays game control buttons (pause, restart)
 */

import React from 'react';
import { GameControlsProps, GameState } from '../types/game.types';
import '../styles/GameControls.css';

export const GameControls: React.FC<GameControlsProps> = ({
  gameState,
  onPause,
  onResume,
  onRestart,
  disabled = false,
  className = '',
}) => {
  const isPaused = gameState === GameState.PAUSED;
  const isRunning = gameState === GameState.RUNNING;
  const isGameOver = gameState === GameState.GAME_OVER;
  const canPause = isRunning && !disabled;
  const canResume = isPaused && !disabled;
  const canRestart = (isPaused || isGameOver || gameState === GameState.READY) && !disabled;

  const handlePauseClick = () => {
    if (canPause) {
      onPause();
    }
  };

  const handleResumeClick = () => {
    if (canResume) {
      onResume();
    }
  };

  const handleRestartClick = () => {
    if (canRestart) {
      onRestart();
    }
  };

  const getPauseButtonLabel = () => {
    if (isPaused) return 'Resume';
    return 'Pause';
  };

  return (
    <div className={`game-controls ${className}`}>
      <div className="button-group">
        {/* Pause/Resume Button */}
        <button
          className="btn-icon"
          onClick={isPaused ? handleResumeClick : handlePauseClick}
          disabled={!canPause && !canResume}
          aria-label={isPaused ? 'Resume game' : 'Pause game'}
          title={getPauseButtonLabel()}
          type="button"
        >
          {isPaused ? (
            // Play icon
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M8 5v14l11-7z"/>
            </svg>
          ) : (
            // Pause icon
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          )}
        </button>

        {/* Restart Button */}
        <button
          className="btn-icon"
          onClick={handleRestartClick}
          disabled={!canRestart}
          aria-label="Restart game"
          title="Restart"
          type="button"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
          </svg>
        </button>
      </div>
    </div>
  );
};
