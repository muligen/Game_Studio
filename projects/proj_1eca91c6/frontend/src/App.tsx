/**
 * Example App - Snake Game
 *
 * Demonstrates usage of the SnakeGame UI components
 */

import React, { useState } from 'react';
import { SnakeGame } from './components/SnakeGame';
import { GameState } from './types/game.types';
import './styles/SnakeGame.css';

function App() {
  const [gameState, setGameState] = useState<GameState>(GameState.READY);
  const [score, setScore] = useState(0);
  const [highScore, setHighScore] = useState(0);

  const handleStateChange = (state: GameState) => {
    setGameState(state);
    console.log('Game state changed:', state);
  };

  const handleScoreChange = (newScore: number) => {
    setScore(newScore);
    if (newScore > highScore) {
      setHighScore(newScore);
    }
  };

  return (
    <div className="app">
      <SnakeGame
        config={{
          gridSize: 10,
          initialSpeed: 500,
          enableWalls: true,
          enableSelfCollision: true,
          foodGrowthRate: 1,
        }}
        onStateChange={handleStateChange}
        onScoreChange={handleScoreChange}
      />
    </div>
  );
}

export default App;
