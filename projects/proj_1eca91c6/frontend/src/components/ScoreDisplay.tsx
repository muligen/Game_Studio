/**
 * ScoreDisplay Component
 *
 * Displays current score and high score with animations
 */

import React, { useEffect, useState, useRef } from 'react';
import { ScoreDisplayProps } from '../types/game.types';
import '../styles/ScoreDisplay.css';

export const ScoreDisplay: React.FC<ScoreDisplayProps> = ({
  score,
  highScore,
  className = '',
  showAnimation = true,
}) => {
  const [displayScore, setDisplayScore] = useState(score);
  const [isAnimating, setIsAnimating] = useState(false);
  const previousScoreRef = useRef(score);
  const animationTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (score !== previousScoreRef.current && score > previousScoreRef.current) {
      // Score increased - animate
      if (showAnimation) {
        setIsAnimating(true);

        // Count-up animation
        const duration = 300;
        const steps = 10;
        const increment = (score - previousScoreRef.current) / steps;
        let currentStep = 0;

        const animateScore = () => {
          currentStep++;
          const newDisplayScore = Math.round(
            previousScoreRef.current + increment * currentStep
          );
          setDisplayScore(newDisplayScore);

          if (currentStep < steps) {
            animationTimeoutRef.current = setTimeout(animateScore, duration / steps);
          } else {
            setDisplayScore(score);
            setTimeout(() => setIsAnimating(false), 150);
          }
        };

        animateScore();
      } else {
        setDisplayScore(score);
      }

      previousScoreRef.current = score;
    } else if (score !== displayScore) {
      // Score changed (not increased) - just update
      setDisplayScore(score);
      previousScoreRef.current = score;
    }
  }, [score, showAnimation, displayScore]);

  useEffect(() => {
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, []);

  const formatScore = (value: number): string => {
    return value.toString().padStart(3, '0');
  };

  return (
    <div className={`score-display ${className}`}>
      <div className="score-item">
        <span className="score-label">Score:</span>
        <span
          className={`score-value ${isAnimating ? 'score-update' : ''}`}
          aria-live="polite"
          aria-atomic="true"
        >
          {formatScore(displayScore)}
        </span>
      </div>

      <div className="score-item">
        <span className="score-label">Best:</span>
        <span
          className="high-score-value"
          aria-live="off"
        >
          {formatScore(highScore)}
        </span>
      </div>
    </div>
  );
};
