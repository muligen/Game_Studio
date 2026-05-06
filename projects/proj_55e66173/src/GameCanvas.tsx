/**
 * GameCanvas Component
 * Renders the game using Canvas API
 */

import React, { useRef, useEffect } from 'react';
import { Position, GameConfig, DEFAULT_GAME_CONFIG } from './types';

interface GameCanvasProps {
  snake: Position[];
  food: Position;
  gameState: string;
  config?: GameConfig;
  canvasSize: number;
}

export const GameCanvas: React.FC<GameCanvasProps> = ({
  snake,
  food,
  gameState,
  config = DEFAULT_GAME_CONFIG,
  canvasSize
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.warn('Canvas context not available');
      return;
    }

    // Clear canvas
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Calculate cell size with padding
    const padding = 2;
    const cellSize = canvas.width / config.gridSize;
    const drawSize = cellSize - padding * 2;

    // Draw snake
    snake.forEach((segment, index) => {
      const x = segment.x * cellSize + padding;
      const y = segment.y * cellSize + padding;

      if (index === 0) {
        // Snake head
        ctx.fillStyle = '#22c55e';
      } else {
        // Snake body (gradient effect)
        const gradient = 1 - (index / snake.length) * 0.5;
        ctx.fillStyle = `rgba(74, 222, 128, ${gradient})`;
      }

      ctx.fillRect(x, y, drawSize, drawSize);

      // Add slight border for definition
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.strokeRect(x, y, drawSize, drawSize);
    });

    // Draw food with pulsing effect
    const foodX = food.x * cellSize + padding;
    const foodY = food.y * cellSize + padding;

    // Pulsing effect for food
    const pulse = Math.sin(performance.now() / 200) * 0.2 + 0.8;
    ctx.fillStyle = `rgba(239, 68, 68, ${pulse})`;
    ctx.beginPath();
    ctx.arc(
      foodX + drawSize / 2,
      foodY + drawSize / 2,
      drawSize / 2,
      0,
      Math.PI * 2
    );
    ctx.fill();

    // Food glow
    ctx.shadowColor = '#ef4444';
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.shadowBlur = 0;

  }, [snake, food, gameState, config, canvasSize]);

  return (
    <canvas
      ref={canvasRef}
      width={canvasSize}
      height={canvasSize}
      style={{
        background: '#1e293b',
        borderRadius: '10px',
        display: 'block',
        width: '100%',
        height: '100%',
        boxShadow: 'inset 0 0 20px rgba(0, 0, 0, 0.5)'
      }}
    />
  );
};
