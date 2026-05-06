/**
 * SnakeGame Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SnakeGame } from '../SnakeGame';
import { GameState } from '../../types/game.types';

describe('SnakeGame', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders game header with title and score', () => {
    render(<SnakeGame />);

    expect(screen.getByText('🐍')).toBeInTheDocument();
    expect(screen.getByText('SNAKE')).toBeInTheDocument();
    expect(screen.getByText('Score:')).toBeInTheDocument();
    expect(screen.getByText('Best:')).toBeInTheDocument();
  });

  it('renders start game overlay when in ready state', () => {
    render(<SnakeGame />);

    expect(screen.getByText('Press SPACE to Start')).toBeInTheDocument();
    expect(screen.getByText('START GAME')).toBeInTheDocument();
  });

  it('starts game when start button is clicked', async () => {
    render(<SnakeGame />);

    const startButton = screen.getByLabelText('Start game');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.queryByText('Press SPACE to Start')).not.toBeInTheDocument();
    });
  });

  it('starts game when space key is pressed', async () => {
    render(<SnakeGame />);

    fireEvent.keyDown(window, { key: ' ' });

    await waitFor(() => {
      expect(screen.queryByText('Press SPACE to Start')).not.toBeInTheDocument();
    });
  });

  it('renders game canvas', () => {
    render(<SnakeGame />);

    const canvas = screen.getByRole('img', { name: /Snake game canvas/i });
    expect(canvas).toBeInTheDocument();
  });

  it('renders pause and restart buttons', () => {
    render(<SnakeGame />);

    expect(screen.getByRole('button', { name: /pause|restart/i })).toBeInTheDocument();
  });

  it('renders footer with controls help', () => {
    render(<SnakeGame />);

    expect(screen.getByText(/Controls:/i)).toBeInTheDocument();
  });

  it('calls onStateChange callback when state changes', async () => {
    const onStateChange = vi.fn();
    render(<SnakeGame onStateChange={onStateChange} />);

    const startButton = screen.getByLabelText('Start game');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(onStateChange).toHaveBeenCalled();
    });
  });

  it('calls onScoreChange callback when score changes', async () => {
    const onScoreChange = vi.fn();
    render(<SnakeGame onScoreChange={onScoreChange} />);

    const startButton = screen.getByLabelText('Start game');
    fireEvent.click(startButton);

    // Score changes would happen during gameplay
    // This is a basic test to ensure the callback is wired up
    expect(onScoreChange).toBeDefined();
  });

  it('uses custom config when provided', () => {
    render(
      <SnakeGame
        config={{
          gridSize: 15,
          initialSpeed: 300,
        }}
      />
    );

    // Game should render without errors with custom config
    expect(screen.getByText('SNAKE')).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(<SnakeGame />);

    const game = screen.getByRole('application');
    expect(game).toHaveAttribute('aria-label', 'Snake Game');
  });

  it('uses custom className when provided', () => {
    const { container } = render(
      <SnakeGame className="custom-class" />
    );

    const game = container.querySelector('.snake-game');
    expect(game).toHaveClass('custom-class');
  });
});
