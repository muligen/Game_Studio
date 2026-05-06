/**
 * GameCanvas Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GameCanvas } from '../GameCanvas';
import { GameState } from '../../types/game.types';

describe('GameCanvas', () => {
  const mockGameData = {
    snake: [
      { x: 5, y: 5, index: 0 },
      { x: 4, y: 5, index: 1 },
      { x: 3, y: 5, index: 2 },
    ],
    food: { x: 7, y: 7, id: 'food-7-7' },
    score: 10,
    highScore: 50,
    gridWidth: 10,
    gridHeight: 10,
  };

  it('renders canvas element with correct dimensions', () => {
    render(
      <GameCanvas
        gameState={GameState.RUNNING}
        gameData={mockGameData}
        cellSize={40}
      />
    );

    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
    expect(canvas).toHaveAttribute('aria-label', 'Snake game canvas');
  });

  it('uses custom className when provided', () => {
    const { container } = render(
      <GameCanvas
        gameState={GameState.RUNNING}
        gameData={mockGameData}
        className="custom-class"
      />
    );

    const wrapper = container.querySelector('.game-canvas-wrapper');
    expect(wrapper).toHaveClass('custom-class');
  });

  it('calls onRender callback when rendering', () => {
    const onRender = vi.fn();

    render(
      <GameCanvas
        gameState={GameState.RUNNING}
        gameData={mockGameData}
        onRender={onRender}
      />
    );

    expect(onRender).toHaveBeenCalled();
  });

  it('has correct accessibility attributes', () => {
    render(
      <GameCanvas
        gameState={GameState.RUNNING}
        gameData={mockGameData}
      />
    );

    const canvas = screen.getByRole('img');
    expect(canvas).toHaveAttribute(
      'aria-description',
      'Game area with 10x10 grid'
    );
  });
});
