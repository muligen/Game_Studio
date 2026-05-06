/**
 * GameOverScreen Component
 *
 * Overlay displayed when game ends
 */

import React from 'react';
import { GameOverScreenProps } from '../types/game.types';
import '../styles/GameOverScreen.css';

export const GameOverScreen: React.FC<GameOverScreenProps> = ({
  score,
  highScore,
  onRestart,
  isNewHighScore = false,
  className = '',
}) => {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onRestart();
    }
  };

  return (
    <div
      className={`game-over-overlay ${className}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="game-over-title"
      aria-describedby="final-score-description"
    >
      <h2
        id="game-over-title"
        className="game-over-title"
      >
        GAME OVER
      </h2>

      {isNewHighScore && (
        <div className="new-high-score-badge" role="status" aria-live="polite">
          🏆 NEW HIGH SCORE! 🏆
        </div>
      )}

      <p
        id="final-score-description"
        className="final-score"
      >
        Final Score:{' '}
        <span className="final-score-value">{score}</span>
      </p>

      <div className="game-over-stats">
        <div className="stat-item">
          <span className="stat-label">Your Score</span>
          <span className="stat-value">{score}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Best Score</span>
          <span className="stat-value">{highScore}</span>
        </div>
      </div>

      <button
        className="btn-primary"
        onClick={onRestart}
        onKeyDown={handleKeyDown}
        autoFocus
        aria-label="Play again"
      >
        PLAY AGAIN
      </button>

      <div className="game-over-hint">
        Press <kbd>Enter</kbd> or <kbd>Space</kbd> to restart
      </div>
    </div>
  );
};
