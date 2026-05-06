/**
 * GameControls Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GameControls } from '../GameControls';
import { GameState } from '../../types/game.types';

describe('GameControls', () => {
  const mockCallbacks = {
    onPause: vi.fn(),
    onResume: vi.fn(),
    onRestart: vi.fn(),
  };

  it('renders pause and restart buttons', () => {
    render(
      <GameControls
        gameState={GameState.RUNNING}
        {...mockCallbacks}
      />
    );

    expect(screen.getByLabelText('Pause game')).toBeInTheDocument();
    expect(screen.getByLabelText('Restart game')).toBeInTheDocument();
  });

  it('calls onPause when pause button is clicked during running state', () => {
    render(
      <GameControls
        gameState={GameState.RUNNING}
        {...mockCallbacks}
      />
    );

    const pauseButton = screen.getByLabelText('Pause game');
    fireEvent.click(pauseButton);

    expect(mockCallbacks.onPause).toHaveBeenCalledTimes(1);
  });

  it('calls onResume when resume button is clicked during paused state', () => {
    render(
      <GameControls
        gameState={GameState.PAUSED}
        {...mockCallbacks}
      />
    );

    const resumeButton = screen.getByLabelText('Resume game');
    fireEvent.click(resumeButton);

    expect(mockCallbacks.onResume).toHaveBeenCalledTimes(1);
  });

  it('calls onRestart when restart button is clicked', () => {
    render(
      <GameControls
        gameState={GameState.PAUSED}
        {...mockCallbacks}
      />
    );

    const restartButton = screen.getByLabelText('Restart game');
    fireEvent.click(restartButton);

    expect(mockCallbacks.onRestart).toHaveBeenCalledTimes(1);
  });

  it('disables buttons when disabled prop is true', () => {
    render(
      <GameControls
        gameState={GameState.RUNNING}
        {...mockCallbacks}
        disabled={true}
      />
    );

    const pauseButton = screen.getByLabelText('Pause game');
    const restartButton = screen.getByLabelText('Restart game');

    expect(pauseButton).toBeDisabled();
    expect(restartButton).toBeDisabled();
  });

  it('uses custom className when provided', () => {
    const { container } = render(
      <GameControls
        gameState={GameState.RUNNING}
        {...mockCallbacks}
        className="custom-class"
      />
    );

    const controls = container.querySelector('.game-controls');
    expect(controls).toHaveClass('custom-class');
  });
});
