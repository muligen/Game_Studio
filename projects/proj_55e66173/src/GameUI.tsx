/**
 * GameUI Component
 * Provides UI elements for all game states
 */

import React from 'react';
import { GameState } from './types';

interface GameUIProps {
  gameState: GameState;
  score: number;
  highScore: number;
  isNewHighScore: boolean;
  fps: number;
  onStartGame: () => void;
  onResumeGame: () => void;
  onRestartGame: () => void;
}

export const GameUI: React.FC<GameUIProps> = ({
  gameState,
  score,
  highScore,
  isNewHighScore,
  fps,
  onStartGame,
  onResumeGame,
  onRestartGame
}) => {
  return (
    <>
      {/* Start Screen */}
      {gameState === GameState.Menu && (
        <div className="overlay">
          <h2>贪吃蛇</h2>
          <p>使用方向键或WASD控制蛇移动</p>
          <p className="high-score">历史最高分: {highScore}</p>
          <button className="btn" onClick={onStartGame}>
            开始游戏
          </button>
        </div>
      )}

      {/* Pause Screen */}
      {gameState === GameState.Paused && (
        <div className="overlay">
          <h2 className="pause-text">PAUSED</h2>
          <p>按 Esc 或 P 继续</p>
          <button className="btn" onClick={onResumeGame}>
            继续游戏
          </button>
        </div>
      )}

      {/* Game Over Screen */}
      {gameState === GameState.GameOver && (
        <div className="overlay">
          <h2>游戏结束</h2>
          <div className="game-over-score">
            得分: <span>{score}</span>
          </div>
          <p className="high-score-message">
            {isNewHighScore ? (
              <span className="new-high-score">🎉 新纪录！</span>
            ) : (
              <span>历史最高分: {highScore}</span>
            )}
          </p>
          <button className="btn" onClick={onRestartGame}>
            重新开始
          </button>
        </div>
      )}

      {/* FPS Counter (show in all states) */}
      <div className="fps-counter">FPS: {fps}</div>
    </>
  );
};

interface HUDProps {
  score: number;
  highScore: number;
}

export const HUD: React.FC<HUDProps> = ({ score, highScore }) => {
  return (
    <div className="scores">
      <div className="score-item">
        <span className="score-label">分数</span>
        <span>{score}</span>
      </div>
      <div className="score-item">
        <span className="score-label">最高分</span>
        <span>{highScore}</span>
      </div>
    </div>
  );
};
