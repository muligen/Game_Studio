/**
 * ScoreDisplay Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScoreDisplay } from '../ScoreDisplay';

describe('ScoreDisplay', () => {
  it('renders current score and high score', () => {
    render(
      <ScoreDisplay
        score={10}
        highScore={50}
      />
    );

    expect(screen.getByText('Score:')).toBeInTheDocument();
    expect(screen.getByText('010')).toBeInTheDocument();
    expect(screen.getByText('Best:')).toBeInTheDocument();
    expect(screen.getByText('050')).toBeInTheDocument();
  });

  it('pads scores with zeros', () => {
    render(
      <ScoreDisplay
        score={5}
        highScore={100}
      />
    );

    expect(screen.getByText('005')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('uses custom className when provided', () => {
    const { container } = render(
      <ScoreDisplay
        score={0}
        highScore={0}
        className="custom-class"
      />
    );

    const display = container.querySelector('.score-display');
    expect(display).toHaveClass('custom-class');
  });

  it('has correct ARIA attributes', () => {
    render(
      <ScoreDisplay
        score={10}
        highScore={50}
      />
    );

    const scoreValue = screen.getByText('010');
    expect(scoreValue).toHaveAttribute('aria-live', 'polite');
    expect(scoreValue).toHaveAttribute('aria-atomic', 'true');
  });
});
