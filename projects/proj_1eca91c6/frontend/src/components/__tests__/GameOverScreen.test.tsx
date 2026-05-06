/**
 * GameOverScreen Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GameOverScreen } from '../GameOverScreen';

describe('GameOverScreen', () => {
  const mockOnRestart = vi.fn();

  it('renders game over message and final score', () => {
    render(
      <GameOverScreen
        score={10}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('GAME OVER')).toBeInTheDocument();
    expect(screen.getByText(/Final Score:/)).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('displays new high score badge when isNewHighScore is true', () => {
    render(
      <GameOverScreen
        score={100}
        highScore={50}
        onRestart={mockOnRestart}
        isNewHighScore={true}
      />
    );

    expect(screen.getByText(/NEW HIGH SCORE/)).toBeInTheDocument();
  });

  it('does not display new high score badge when score is not high score', () => {
    render(
      <GameOverScreen
        score={30}
        highScore={50}
        onRestart={mockOnRestart}
        isNewHighScore={false}
      />
    );

    expect(screen.queryByText(/NEW HIGH SCORE/)).not.toBeInTheDocument();
  });

  it('calls onRestart when play again button is clicked', () => {
    render(
      <GameOverScreen
        score={10}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    const playAgainButton = screen.getByLabelText('Play again');
    fireEvent.click(playAgainButton);

    expect(mockOnRestart).toHaveBeenCalledTimes(1);
  });

  it('calls onRestart when Enter key is pressed', () => {
    render(
      <GameOverScreen
        score={10}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    const overlay = screen.getByRole('dialog');
    fireEvent.keyDown(overlay, { key: 'Enter' });

    expect(mockOnRestart).toHaveBeenCalledTimes(1);
  });

  it('calls onRestart when Space key is pressed', () => {
    render(
      <GameOverScreen
        score={10}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    const overlay = screen.getByRole('dialog');
    fireEvent.keyDown(overlay, { key: ' ' });

    expect(mockOnRestart).toHaveBeenCalledTimes(1);
  });

  it('displays score statistics', () => {
    render(
      <GameOverScreen
        score={25}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('Your Score')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('Best Score')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(
      <GameOverScreen
        score={10}
        highScore={50}
        onRestart={mockOnRestart}
      />
    );

    const overlay = screen.getByRole('dialog');
    expect(overlay).toHaveAttribute('aria-modal', 'true');
    expect(overlay).toHaveAttribute('aria-labelledby', 'game-over-title');
    expect(overlay).toHaveAttribute('aria-describedby', 'final-score-description');
  });
});
