/**
 * Enhanced GameCanvas Component
 *
 * Optimized canvas rendering with FPS tracking, dirty rectangle optimization,
 * and batch rendering for high-performance game visualization
 */

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { GameCanvasProps, GameState } from '../types/game.types';
import { RenderingEngine, createRenderingEngine, RenderPerformanceMetrics } from '../utils/renderingEngine';
import { PerformanceMonitor, createPerformanceMonitor, formatPerformanceReport } from '../utils/performanceMonitor';
import '../styles/GameCanvas.css';

export interface GameCanvasEnhancedProps extends GameCanvasProps {
  targetFPS?: number;
  enablePerformanceMonitoring?: boolean;
  showDebugInfo?: boolean;
  onPerformanceUpdate?: (metrics: RenderPerformanceMetrics) => void;
}

export const GameCanvasEnhanced: React.FC<GameCanvasEnhancedProps> = ({
  gameState,
  gameData,
  cellSize = 40,
  className = '',
  onRender,
  targetFPS = 60,
  enablePerformanceMonitoring = true,
  showDebugInfo = false,
  onPerformanceUpdate,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderingEngineRef = useRef<RenderingEngine | null>(null);
  const performanceMonitorRef = useRef<PerformanceMonitor | null>(null);
  const previousScoreRef = useRef<number>(0);
  const previousSnakeRef = useRef<string>('');
  const previousFoodRef = useRef<string>('');
  const [currentFPS, setCurrentFPS] = useState<number>(0);

  // Initialize rendering engine
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Create rendering engine
    const engine = createRenderingEngine(canvas, {
      targetFPS,
      enableDirtyRectangles: true,
      enablePerformanceMetrics: enablePerformanceMonitoring,
      debugMode: showDebugInfo,
    });

    renderingEngineRef.current = engine;

    // Create performance monitor if enabled
    if (enablePerformanceMonitoring) {
      const monitor = createPerformanceMonitor({
        targetFPS,
        minAcceptableFPS: 30,
      });
      performanceMonitorRef.current = monitor;
      monitor.start();
    }

    return () => {
      engine.destroy();
      if (performanceMonitorRef.current) {
        performanceMonitorRef.current.stop();
      }
    };
  }, [targetFPS, enablePerformanceMonitoring, showDebugInfo]);

  // Update performance metrics
  useEffect(() => {
    if (!renderingEngineRef.current || !enablePerformanceMonitoring) return;

    const engine = renderingEngineRef.current;
    const metrics = engine.getMetrics();

    setCurrentFPS(metrics.fps);

    if (onPerformanceUpdate) {
      onPerformanceUpdate(metrics);
    }

    // Record metrics in performance monitor
    if (performanceMonitorRef.current) {
      performanceMonitorRef.current.recordFrame(
        metrics.fps,
        metrics.frameTime,
        metrics.renderTime
      );
    }
  }, [gameState, gameData, enablePerformanceMonitoring, onPerformanceUpdate]);

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
      // Draw snake head with gradient
      const gradient = ctx.createRadialGradient(
        px + size / 2, py + size / 2, 2,
        px + size / 2, py + size / 2, size / 2
      );
      gradient.addColorStop(0, '#66BB6A');
      gradient.addColorStop(1, '#4CAF50');

      ctx.fillStyle = gradient;
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

  // Draw food with animation
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

    // Draw apple with gradient
    const gradient = ctx.createRadialGradient(
      px + size / 2 - 3, py + size / 2, 2,
      px + size / 2, py + size / 2 + 4, 12
    );
    gradient.addColorStop(0, '#FF6B6B');
    gradient.addColorStop(1, '#E74C3C');

    ctx.fillStyle = gradient;
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

  // Main render function with optimizations
  const render = useCallback(() => {
    const engine = renderingEngineRef.current;
    if (!engine) return;

    const ctx = engine.getContext();
    const canvas = engine.getCanvas();

    // Start frame
    engine.beginFrame();

    // Get canvas dimensions
    const width = gameData.gridWidth * cellSize;
    const height = gameData.gridHeight * cellSize;

    // Clear and redraw background
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

    // Update previous state
    previousScoreRef.current = gameData.score;

    // End frame
    engine.endFrame();

    // Call custom render callback if provided
    if (onRender) {
      onRender(ctx);
    }
  }, [gameData, cellSize, drawGrid, drawSnakeSegment, drawFood, onRender]);

  // Render on state changes
  useEffect(() => {
    render();
  }, [render, gameState]);

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
      {enablePerformanceMonitoring && (
        <div className="performance-indicator" aria-live="polite">
          <span className="fps-display">FPS: {currentFPS}</span>
          {currentFPS < 30 && (
            <span className="fps-warning" aria-label="Low FPS warning">
              ⚠️ Low performance
            </span>
          )}
        </div>
      )}
    </div>
  );
};
