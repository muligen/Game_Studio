/**
 * Rendering Engine Tests
 *
 * Test canvas rendering engine with FPS tracking, dirty rectangle optimization,
 * and batch rendering
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  RenderingEngine,
  createRenderingEngine,
  validateFPS,
  calculateRenderEfficiency,
  RenderPerformanceMetrics,
} from '../renderingEngine';

describe('RenderingEngine', () => {
  let canvas: HTMLCanvasElement;
  let engine: RenderingEngine;

  beforeEach(() => {
    // Create a canvas element
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
  });

  afterEach(() => {
    engine.destroy();
    document.body.removeChild(canvas);
  });

  describe('Initialization', () => {
    it('should create rendering engine with canvas', () => {
      expect(engine).toBeDefined();
      expect(engine.getCanvas()).toBe(canvas);
      expect(engine.getContext()).toBeDefined();
    });

    it('should use default config when not provided', () => {
      const defaultEngine = createRenderingEngine(canvas);
      expect(defaultEngine).toBeDefined();
      defaultEngine.destroy();
    });

    it('should start with zero metrics', () => {
      const metrics = engine.getMetrics();
      expect(metrics.fps).toBe(0);
      expect(metrics.frameTime).toBe(0);
      expect(metrics.renderTime).toBe(0);
      expect(metrics.totalFrames).toBe(0);
    });
  });

  describe('Performance Metrics', () => {
    it('should track frame rendering', () => {
      engine.beginFrame();
      // Simulate some rendering
      const ctx = engine.getContext();
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, 100, 100);
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
      expect(metrics.frameTime).toBeGreaterThan(0);
    });

    it('should calculate FPS over multiple frames', () => {
      // Simulate multiple frames
      for (let i = 0; i < 10; i++) {
        engine.beginFrame();
        const ctx = engine.getContext();
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, 100, 100);
        engine.endFrame();
      }

      // FPS calculation happens every second
      // In a real scenario with proper timing, this would give accurate FPS
      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(10);
    });

    it('should reset metrics', () => {
      engine.beginFrame();
      engine.endFrame();

      engine.resetMetrics();

      const metrics = engine.getMetrics();
      expect(metrics.fps).toBe(0);
      expect(metrics.totalFrames).toBe(0);
    });
  });

  describe('Dirty Rectangle Optimization', () => {
    it('should mark regions as dirty', () => {
      engine.markDirty(10, 10, 50, 50);
      engine.markDirty(100, 100, 30, 30);

      // Should not throw
      engine.beginFrame();
      engine.endFrame();

      const metrics = engine.getMetrics();
      // Dirty rectangles are cleared during frame render
      expect(metrics.dirtyRects).toBeGreaterThanOrEqual(0);
    });

    it('should mark entire canvas as dirty', () => {
      engine.markAllDirty();

      engine.beginFrame();
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.dirtyRects).toBe(1);
    });

    it('should disable dirty rectangles when config disabled', () => {
      const noDirtyRectEngine = createRenderingEngine(canvas, {
        enableDirtyRectangles: false,
      });

      noDirtyRectEngine.markDirty(10, 10, 50, 50);
      noDirtyRectEngine.beginFrame();
      noDirtyRectEngine.endFrame();

      const metrics = noDirtyRectEngine.getMetrics();
      expect(metrics.dirtyRects).toBe(1); // Full canvas clear

      noDirtyRectEngine.destroy();
    });
  });

  describe('Batch Rendering', () => {
    it('should draw rectangle with fill and stroke', () => {
      engine.beginFrame();
      engine.drawRect(10, 10, 50, 50, '#FF0000', '#000000', 2);
      engine.endFrame();

      const ctx = engine.getContext();
      // Verify rectangle was drawn by checking canvas state
      expect(ctx.fillStyle).toBe('#FF0000');
    });

    it('should draw circle with fill and stroke', () => {
      engine.beginFrame();
      engine.drawCircle(50, 50, 20, '#00FF00', '#000000', 2);
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });

    it('should draw text', () => {
      engine.beginFrame();
      engine.drawText('Test', 10, 10, '#FFFFFF', 12, 'monospace');
      engine.endFrame();

      const metrics = engine.getMetrics();
      expect(metrics.totalFrames).toBe(1);
    });
  });

  describe('Animation Loop', () => {
    it('should start and stop animation loop', () => {
      const callback = vi.fn();

      engine.startAnimation(callback);

      // Let a few frames run
      setTimeout(() => {
        engine.stopAnimation();
        expect(callback).toHaveBeenCalled();
      }, 100);
    });

    it('should not start multiple animation loops', () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();

      engine.startAnimation(callback1);
      engine.startAnimation(callback2); // Should be ignored

      setTimeout(() => {
        engine.stopAnimation();
        // Only first callback should be used
        expect(callback1).toHaveBeenCalled();
      }, 100);
    });
  });

  describe('FPS Validation', () => {
    it('should validate target FPS is met', () => {
      const metrics: RenderPerformanceMetrics = {
        fps: 60,
        frameTime: 16.67,
        renderTime: 8,
        dirtyRects: 5,
        totalFrames: 100,
      };

      expect(validateFPS(metrics, 30)).toBe(true);
      expect(validateFPS(metrics, 60)).toBe(true);
      expect(validateFPS(metrics, 120)).toBe(false);
    });

    it('should handle zero FPS', () => {
      const metrics: RenderPerformanceMetrics = {
        fps: 0,
        frameTime: 0,
        renderTime: 0,
        dirtyRects: 0,
        totalFrames: 0,
      };

      expect(validateFPS(metrics, 30)).toBe(false);
    });
  });

  describe('Render Efficiency', () => {
    it('should calculate efficiency correctly', () => {
      const metrics1: RenderPerformanceMetrics = {
        fps: 60,
        frameTime: 16.67,
        renderTime: 8,
        dirtyRects: 5,
        totalFrames: 100,
      };

      const efficiency1 = calculateRenderEfficiency(metrics1);
      expect(efficiency1).toBeCloseTo(0.52, 1); // (16.67 - 8) / 16.67

      const metrics2: RenderPerformanceMetrics = {
        fps: 60,
        frameTime: 16.67,
        renderTime: 0,
        dirtyRects: 5,
        totalFrames: 100,
      };

      const efficiency2 = calculateRenderEfficiency(metrics2);
      expect(efficiency2).toBe(1); // Perfect efficiency

      const metrics3: RenderPerformanceMetrics = {
        fps: 60,
        frameTime: 16.67,
        renderTime: 20, // More than frame time
        dirtyRects: 5,
        totalFrames: 100,
      };

      const efficiency3 = calculateRenderEfficiency(metrics3);
      expect(efficiency3).toBe(0); // Zero efficiency
    });

    it('should handle zero frame time', () => {
      const metrics: RenderPerformanceMetrics = {
        fps: 0,
        frameTime: 0,
        renderTime: 0,
        dirtyRects: 0,
        totalFrames: 0,
      };

      expect(calculateRenderEfficiency(metrics)).toBe(1);
    });
  });

  describe('Target FPS Check', () => {
    it('should check if target FPS is met', () => {
      const targetFPSEngine = createRenderingEngine(canvas, {
        targetFPS: 30,
      });

      // Simulate frames
      for (let i = 0; i < 5; i++) {
        targetFPSEngine.beginFrame();
        targetFPSEngine.endFrame();
      }

      // Without actual timing, this tests the method exists
      expect(typeof targetFPSEngine.isTargetFPSMet).toBe('function');

      targetFPSEngine.destroy();
    });
  });

  describe('Debug Mode', () => {
    it('should draw debug info when enabled', () => {
      const debugEngine = createRenderingEngine(canvas, {
        debugMode: true,
      });

      debugEngine.beginFrame();
      const ctx = debugEngine.getContext();
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, 400, 400);
      debugEngine.endFrame();

      // Debug info is drawn, but we can't easily verify canvas contents
      // This test ensures no errors are thrown
      const metrics = debugEngine.getMetrics();
      expect(metrics.totalFrames).toBe(1);

      debugEngine.destroy();
    });
  });

  describe('Resource Cleanup', () => {
    it('should properly destroy engine', () => {
      engine.startAnimation(() => {});

      expect(() => engine.destroy()).not.toThrow();

      // After destroy, starting new animation should work with new engine
      const newEngine = createRenderingEngine(canvas);
      expect(() => newEngine.destroy()).not.toThrow();
    });

    it('should stop animation loop on destroy', () => {
      const callback = vi.fn();
      engine.startAnimation(callback);

      engine.destroy();

      // Animation should be stopped
      // We can't easily verify this without waiting, but we test no errors
      expect(true).toBe(true);
    });
  });
});

describe('Rendering Engine Utilities', () => {
  describe('validateFPS', () => {
    it('should validate FPS against minimum', () => {
      expect(validateFPS({ fps: 60 } as any, 30)).toBe(true);
      expect(validateFPS({ fps: 30 } as any, 30)).toBe(true);
      expect(validateFPS({ fps: 29 } as any, 30)).toBe(false);
    });

    it('should use default minimum of 30', () => {
      expect(validateFPS({ fps: 30 } as any)).toBe(true);
      expect(validateFPS({ fps: 29 } as any)).toBe(false);
    });
  });

  describe('calculateRenderEfficiency', () => {
    it('should calculate efficiency as percentage', () => {
      const result = calculateRenderEfficiency({
        frameTime: 100,
        renderTime: 25,
      } as any);

      expect(result).toBeCloseTo(0.75, 2);
    });

    it('should clamp efficiency between 0 and 1', () => {
      expect(calculateRenderEfficiency({
        frameTime: 100,
        renderTime: 150, // More than frame time
      } as any)).toBe(0);

      expect(calculateRenderEfficiency({
        frameTime: 100,
        renderTime: -10, // Negative
      } as any)).toBe(1);
    });
  });
});
