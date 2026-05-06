/**
 * GameCanvas Component
 *
 * Renders the game canvas with snake, food, and grid
 */

import React, { useRef, useEffect, useCallback } from 'react';
import { GameCanvasProps, GameState } from '../types/game.types';
import '../styles/GameCanvas.css';

export const GameCanvas: React.FC<GameCanvasProps> = ({
  gameState,
  gameData,
  cellSize = 40,
  className = '',
  onRender,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const previousScoreRef = useRef<number>(0);

  // Load SVG sprites
  const loadSvgImage = useCallback((svgPath: string): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      // In production, these would be actual file paths
      // For now, we'll draw shapes directly
      resolve(img);
    });
  }, []);

  // Draw grid
  const drawGrid = useCallback((
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ) => {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;

    for (let x = 0; x <= width; x += cellSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    for (let y = 0; y <= height; y += cellSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  }, [cellSize]);

  // Draw snake segment
  const drawSnakeSegment = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    isHead: boolean = false,
    isTail: boolean = false,
    bodyIndex: number = 0
  ) => {
    const px = x * cellSize;
    const py = y * cellSize;
    const size = cellSize;

    if (isHead) {
      // Draw snake head
      ctx.fillStyle = '#4CAF50';
      ctx.strokeStyle = '#388E3C';
      ctx.lineWidth = 3;

      ctx.beginPath();
      ctx.roundRect(px + 2, py + 2, size - 4, size - 4, 6);
      ctx.fill();
      ctx.stroke();

      // Draw eyes
      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(px + 12, py + 14, 4, 0, Math.PI * 2);
      ctx.arc(px + 28, py + 14, 4, 0, Math.PI * 2);
      ctx.fill();

      // Draw pupils
      ctx.fillStyle = '#000000';
      ctx.beginPath();
      ctx.arc(px + 13, py + 14, 2, 0, Math.PI * 2);
      ctx.arc(px + 29, py + 14, 2, 0, Math.PI * 2);
      ctx.fill();
    } else if (isTail) {
      // Draw snake tail (smaller, centered)
      ctx.fillStyle = '#C8E6C9';
      ctx.strokeStyle = '#388E3C';
      ctx.lineWidth = 2;

      const tailSize = size - 12;
      const offset = 6;
      ctx.beginPath();
      ctx.roundRect(px + offset, py + offset, tailSize, tailSize, 4);
      ctx.fill();
      ctx.stroke();
    } else {
      // Draw snake body with gradient effect
      const colors = ['#66BB6A', '#81C784', '#A5D6A7'];
      const colorIndex = bodyIndex % colors.length;
      ctx.fillStyle = colors[colorIndex];
      ctx.strokeStyle = '#388E3C';
      ctx.lineWidth = 2;

      ctx.beginPath();
      ctx.roundRect(px + 3, py + 3, size - 6, size - 6, 4);
      ctx.fill();
      ctx.stroke();
    }
  }, [cellSize]);

  // Draw food
  const drawFood = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    hasScoreChanged: boolean
  ) => {
    const px = x * cellSize;
    const py = y * cellSize;
    const size = cellSize;

    ctx.save();

    // Add pulse animation if score just changed
    if (hasScoreChanged) {
      const scale = 1.1;
      ctx.translate(px + size / 2, py + size / 2);
      ctx.scale(scale, scale);
      ctx.translate(-(px + size / 2), -(py + size / 2));
    }

    // Draw apple body
    ctx.fillStyle = '#E74C3C';
    ctx.strokeStyle = '#C0392B';
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.arc(px + size / 2, py + size / 2 + 4, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Draw stem
    ctx.fillStyle = '#8B4513';
    ctx.fillRect(px + size / 2 - 2, py + 8, 4, 8);

    // Draw leaf
    ctx.fillStyle = '#4CAF50';
    ctx.beginPath();
    ctx.ellipse(px + size / 2 + 6, py + 10, 6, 3, Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }, [cellSize]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    const width = gameData.gridWidth * cellSize;
    const height = gameData.gridHeight * cellSize;
    ctx.clearRect(0, 0, width, height);

    // Draw background
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    drawGrid(ctx, width, height);

    // Draw food
    if (gameData.food) {
      const scoreChanged = gameData.score > previousScoreRef.current;
      drawFood(ctx, gameData.food.x, gameData.food.y, scoreChanged);
    }

    // Draw snake
    if (gameData.snake.length > 0) {
      gameData.snake.forEach((segment, index) => {
        const isHead = index === 0;
        const isTail = index === gameData.snake.length - 1;
        drawSnakeSegment(ctx, segment.x, segment.y, isHead, isTail, index);
      });
    }

    // Update previous score
    previousScoreRef.current = gameData.score;

    // Call custom render callback if provided
    if (onRender) {
      onRender(ctx);
    }
  }, [gameData, cellSize, drawGrid, drawSnakeSegment, drawFood, onRender]);

  useEffect(() => {
    render();
  }, [render, gameState]);

  // Handle keyboard events
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === ' ' && gameState === GameState.RUNNING) {
        event.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [gameState]);

  const canvasWidth = gameData.gridWidth * cellSize;
  const canvasHeight = gameData.gridHeight * cellSize;

  return (
    <div className={`game-canvas-wrapper ${className}`}>
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        className="game-canvas"
        aria-label="Snake game canvas"
        role="img"
        aria-description={`Game area with ${gameData.gridWidth}x${gameData.gridHeight} grid`}
      />
    </div>
  );
};
