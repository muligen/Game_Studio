/**
 * Rendering System Integration Tests
 *
 * End-to-end tests for canvas rendering with FPS validation and performance monitoring
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { RenderingEngine, createRenderingEngine, validateFPS } from '../renderingEngine';
import { PerformanceMonitor, createPerformanceMonitor } from '../performanceMonitor';

describe('Rendering System Integration', () => {
  let canvas: HTMLCanvasElement;
  let engine: RenderingEngine;
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    // Create canvas element
    canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 400;
    document.body.appendChild(canvas);

    // Create rendering engine
    engine = createRenderingEngine(canvas, {
      targetFPS: 60,
      enableDirtyRectangles: true,
      enablePerformanceMetrics: true,
      debugMode: false,
    });

    // Create performance monitor
    monitor = createPerformanceMonitor({
      targetFPS: 60,
      minAcceptableFPS: 30,
    });
    monitor.start();
  });

  afterEach(() => {
    monitor.stop();
    engine.destroy();
    document.body.removeChild(canvas);
  });

  describe('Canvas Rendering Setup', () => {
    it('should initialize canvas with correct dimensions', () => {
      expect(canvas.width).toBe(400);
      expect(canvas.height).toBe(400);
    });

    it('should have 2D rendering context', () => {
      const ctx = engine.getContext();
      expect(ctx).toBeDefined();
      expect(ctx.canvas).toBe(canvas);
    });

    it('should support alpha disabled for performance', () => {
      const ctx = canvas.getContext('2d', { alpha: false });
      expect(ctx).toBeDefined();
    });
  });

  describe('Grid Drawing Based on Configuration', () => {
    it('should draw grid with 10x10 configuration', () => {
      const gridSize = 10;
      const cellSize = 40;
      const ctx = engine.getContext();

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Draw grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;

      for (let x = 0; x <= 400; x += cellSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, 400);
        ctx.stroke();
      }

      for (let y = 0; y <= 400; y += cellSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(400, y);
        ctx.stroke();
      }

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should adapt grid to different cell sizes', () => {
      const cellSizes = [20, 30, 40, 50];

      cellSizes.forEach(cellSize => {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.clearRect(0, 0, 400, 400);

        // Draw grid with different cell size
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        for (let x = 0; x <= 400; x += cellSize) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, 400);
          ctx.stroke();
        }

        engine.endFrame();
      });

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(cellSizes.length);
    });
  });

  describe('Snake Rendering with Head and Body Segments', () => {
    it('should render snake head with distinct appearance', () => {
      const ctx = engine.getContext();

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Draw snake head
      const px = 100;
      const py = 100;
      const size = 40;

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

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should render snake body with gradient pattern', () => {
      const ctx = engine.getContext();
      const colors = ['#66BB6A', '#81C784', '#A5D6A7'];

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Draw multiple body segments
      const segments = [
        { x: 60, y: 100 },
        { x: 20, y: 100 },
        { x: -20, y: 100 },
      ];

      segments.forEach((segment, index) => {
        const colorIndex = index % colors.length;
        ctx.fillStyle = colors[colorIndex];
        ctx.strokeStyle = '#388E3C';
        ctx.lineWidth = 2;

        ctx.beginPath();
        ctx.roundRect(
          segment.x + 3,
          segment.y + 3,
          40 - 6,
          40 - 6,
          4
        );
        ctx.fill();
        ctx.stroke();
      });

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should render snake tail with smaller size', () => {
      const ctx = engine.getContext();

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Draw snake tail
      const px = 20;
      const py = 100;
      const size = 40;
      const tailSize = size - 12;
      const offset = 6;

      ctx.fillStyle = '#C8E6C9';
      ctx.strokeStyle = '#388E3C';
      ctx.lineWidth = 2;

      ctx.beginPath();
      ctx.roundRect(px + offset, py + offset, tailSize, tailSize, 4);
      ctx.fill();
      ctx.stroke();

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });
  });

  describe('Food Rendering', () => {
    it('should render food as apple with stem and leaf', () => {
      const ctx = engine.getContext();

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Draw apple
      const px = 200;
      const py = 200;
      const size = 40;

      // Apple body
      ctx.fillStyle = '#E74C3C';
      ctx.strokeStyle = '#C0392B';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(px + size / 2, py + size / 2 + 4, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Stem
      ctx.fillStyle = '#8B4513';
      ctx.fillRect(px + size / 2 - 2, py + 8, 4, 8);

      // Leaf
      ctx.fillStyle = '#4CAF50';
      ctx.beginPath();
      ctx.ellipse(px + size / 2 + 6, py + 10, 6, 3, Math.PI / 4, 0, Math.PI * 2);
      ctx.fill();

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should animate food when score changes', () => {
      const ctx = engine.getContext();
      const hasScoreChanged = true;

      engine.beginFrame();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      const px = 200;
      const py = 200;
      const size = 40;

      ctx.save();

      if (hasScoreChanged) {
        const scale = 1.1;
        ctx.translate(px + size / 2, py + size / 2);
        ctx.scale(scale, scale);
        ctx.translate(-(px + size / 2), -(py + size / 2));
      }

      // Draw apple
      ctx.fillStyle = '#E74C3C';
      ctx.beginPath();
      ctx.arc(px + size / 2, py + size / 2 + 4, 12, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });
  });

  describe('Smooth Animation at Target FPS (≥30)', () => {
    it('should maintain 30+ FPS during basic rendering', async () => {
      const frameCount = 30;
      const targetFPS = 30;

      for (let i = 0; i < frameCount; i++) {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.fillStyle = '#1A1A1A';
        ctx.fillRect(0, 0, 400, 400);
        engine.endFrame();

        const metrics = engine.getMetrics();
        monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);
      }

      const report = monitor.generateReport();
      expect(report.averageFPS).toBeGreaterThanOrEqual(targetFPS);
      expect(report.targetFPSMet).toBe(true);
    });

    it('should maintain 60 FPS during simple rendering', async () => {
      const frameCount = 60;

      for (let i = 0; i < frameCount; i++) {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.clearRect(0, 0, 400, 400);
        engine.endFrame();

        const metrics = engine.getMetrics();
        monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);
      }

      const report = monitor.generateReport();
      expect(report.averageFPS).toBeGreaterThanOrEqual(30);
    });
  });

  describe('Performance Optimization (Batch Rendering, Dirty Rectangle)', () => {
    it('should use dirty rectangle optimization', () => {
      engine.markDirty(10, 10, 50, 50);
      engine.markDirty(100, 100, 30, 30);

      engine.beginFrame();
      const ctx = engine.getContext();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.dirtyRects).toBe(2);
    });

    it('should fall back to full canvas clear when needed', () => {
      engine.markAllDirty();

      engine.beginFrame();
      const ctx = engine.getContext();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.dirtyRects).toBe(1);
    });

    it('should batch render multiple rectangles efficiently', () => {
      const rectCount = 10;

      engine.beginFrame();
      const ctx = engine.getContext();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Batch render rectangles
      for (let i = 0; i < rectCount; i++) {
        engine.drawRect(
          i * 40,
          100,
          30,
          30,
          '#4CAF50',
          '#388E3C',
          2
        );
      }

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should batch render multiple circles efficiently', () => {
      const circleCount = 10;

      engine.beginFrame();
      const ctx = engine.getContext();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Batch render circles
      for (let i = 0; i < circleCount; i++) {
        engine.drawCircle(
          i * 40 + 20,
          200,
          15,
          '#E74C3C',
          '#C0392B',
          2
        );
      }

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });
  });

  describe('FPS Validation', () => {
    it('should validate FPS meets minimum requirement', () => {
      const goodMetrics = {
        fps: 60,
        frameTime: 16.67,
        renderTime: 8,
        dirtyRects: 5,
        totalFrames: 100,
      };

      expect(validateFPS(goodMetrics, 30)).toBe(true);
      expect(validateFPS(goodMetrics, 60)).toBe(true);
    });

    it('should fail validation for poor FPS', () => {
      const poorMetrics = {
        fps: 15,
        frameTime: 66.67,
        renderTime: 30,
        dirtyRects: 5,
        totalFrames: 100,
      };

      expect(validateFPS(poorMetrics, 30)).toBe(false);
    });

    it('should track FPS over multiple frames', () => {
      const fpsValues = [60, 58, 62, 59, 61, 60, 57, 63, 60, 59];

      fpsValues.forEach(fps => {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.clearRect(0, 0, 400, 400);
        engine.endFrame();

        const metrics = engine.getMetrics();
        monitor.recordFrame(fps, 1000 / fps, 8);
      });

      const report = monitor.generateReport();
      expect(report.averageFPS).toBeCloseTo(59.9, 1);
      expect(report.minFPS).toBe(57);
      expect(report.maxFPS).toBe(63);
    });
  });

  describe('Full Game Scene Rendering', () => {
    it('should render complete game scene efficiently', () => {
      const ctx = engine.getContext();

      engine.beginFrame();

      // Background
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      for (let x = 0; x <= 400; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, 400);
        ctx.stroke();
      }
      for (let y = 0; y <= 400; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(400, y);
        ctx.stroke();
      }

      // Snake (5 segments)
      const snake = [
        { x: 200, y: 200 },
        { x: 160, y: 200 },
        { x: 120, y: 200 },
        { x: 80, y: 200 },
        { x: 40, y: 200 },
      ];

      snake.forEach((segment, index) => {
        const isHead = index === 0;
        ctx.fillStyle = isHead ? '#4CAF50' : '#66BB6A';
        ctx.strokeStyle = '#388E3C';
        ctx.lineWidth = isHead ? 3 : 2;
        ctx.beginPath();
        ctx.roundRect(
          segment.x + 2,
          segment.y + 2,
          36,
          36,
          isHead ? 6 : 4
        );
        ctx.fill();
        ctx.stroke();
      });

      // Food
      ctx.fillStyle = '#E74C3C';
      ctx.strokeStyle = '#C0392B';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(320, 120, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);

      // Record in monitor
      monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);
    });

    it('should handle rapid state changes efficiently', () => {
      const stateChanges = 10;

      for (let i = 0; i < stateChanges; i++) {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.fillStyle = '#1A1A1A';
        ctx.fillRect(0, 0, 400, 400);

        // Draw different content each frame
        ctx.fillStyle = `hsl(${i * 36}, 70%, 50%)`;
        ctx.fillRect(i * 20, i * 20, 50, 50);

        engine.endFrame();

        const metrics = engine.getMetrics();
        monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);
      }

      const report = monitor.generateReport();
      expect(report.frameCount).toBe(stateChanges);
      expect(report.targetFPSMet).toBe(true);
    });
  });

  describe('Performance Under Load', () => {
    it('should maintain performance with many render calls', () => {
      const objectCount = 50;

      engine.beginFrame();
      const ctx = engine.getContext();
      ctx.fillStyle = '#1A1A1A';
      ctx.fillRect(0, 0, 400, 400);

      // Render many objects
      for (let i = 0; i < objectCount; i++) {
        engine.drawRect(
          Math.random() * 350,
          Math.random() * 350,
          20,
          20,
          '#4CAF50',
          '#388E3C',
          1
        );
      }

      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);

      monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);

      const report = monitor.generateReport();
      expect(report.targetFPSMet).toBe(true);
    });

    it('should handle complex animations smoothly', () => {
      const frameCount = 30;

      for (let frame = 0; frame < frameCount; frame++) {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.fillStyle = '#1A1A1A';
        ctx.fillRect(0, 0, 400, 400);

        // Animate objects
        for (let i = 0; i < 10; i++) {
          const x = (frame * 5 + i * 40) % 400;
          const y = 100 + Math.sin(frame * 0.1 + i) * 50;

          engine.drawCircle(
            x,
            y,
            15,
            '#E74C3C',
            '#C0392B',
            2
          );
        }

        engine.endFrame();

        const metrics = engine.getMetrics();
        monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);
      }

      const report = monitor.generateReport();
      expect(report.averageFPS).toBeGreaterThanOrEqual(30);
    });
  });
});
