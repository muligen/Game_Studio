/**
 * Snake Game Entry Point
 * Exports the main GameContainer component
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { GameContainer } from './GameContainer';
import './Game.css';

// Mount the game if run directly
if (typeof document !== 'undefined') {
  const rootElement = document.getElementById('root');
  if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(
      <React.StrictMode>
        <GameContainer />
      </React.StrictMode>
    );
  }
}

export { GameContainer };
export { GameCanvas } from './GameCanvas';
export { GameUI, HUD } from './GameUI';
export type { GameState, Position, Direction, GameConfig, GameAction } from './types';
export {
  createInitialSnake,
  createInitialDirection,
  generateFood,
  updateSnake,
  isValidDirectionChange,
  loadHighScore,
  saveHighScore
} from './gameLogic';
