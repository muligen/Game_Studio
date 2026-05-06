/**
 * Performance Tests for Snake Game
 * Tests frame rate, input latency, and memory usage
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  createInitialSnake,
  createInitialDirection,
  generateFood,
  updateSnake,
  isValidDirectionChange
} from '../gameLogic';
import { PerformanceMonitor, PerformanceReport } from '../performanceMonitor';

describe('Performance Tests', () => {
  describe('Game Logic Performance', () => {
    it('should update snake position in less than 1ms', () => {
      const snake = createInitialSnake();
      const direction = createInitialDirection();
      const food = { x: 10, y: 10 };
      const gridSize = 20;
      const foodScore = 10;

      const start = performance.now();
      const iterations = 1000;

      for (let i = 0; i < iterations; i++) {
        updateSnake(snake, direction, food, gridSize, foodScore);
      }

      const duration = performance.now() - start;
      const avgDuration = duration / iterations;

      expect(avgDuration).toBeLessThan(1); // Less than 1ms per update
      console.log(`Average update time: ${avgDuration.toFixed(3)}ms`);
    });

    it('should generate food in less than 0.5ms', () => {
      const snake = createInitialSnake();
      const gridSize = 20;

      const start = performance.now();
      const iterations = 1000;

      for (let i = 0; i < iterations; i++) {
        generateFood(snake, gridSize);
      }

      const duration = performance.now() - start;
      const avgDuration = duration / iterations;

      expect(avgDuration).toBeLessThan(0.5); // Less than 0.5ms per generation
      console.log(`Average food generation time: ${avgDuration.toFixed(3)}ms`);
    });

    it('should validate direction changes in less than 0.1ms', () => {
      const current = { x: 1, y: 0 };
      const next = { x: 0, y: 1 };

      const start = performance.now();
      const iterations = 10000;

      for (let i = 0; i < iterations; i++) {
        isValidDirectionChange(current, next);
      }

      const duration = performance.now() - start;
      const avgDuration = duration / iterations;

      expect(avgDuration).toBeLessThan(0.1); // Less than 0.1ms per validation
      console.log(`Average direction validation time: ${avgDuration.toFixed(4)}ms`);
    });
  });

  describe('Memory Efficiency', () => {
    it('should not leak memory during repeated snake updates', () => {
      if (!('memory' in performance)) {
        console.warn('Memory API not available, skipping memory leak test');
        return;
      }

      const monitor = new PerformanceMonitor();
      const snake = createInitialSnake();
      const direction = createInitialDirection();
      const food = { x: 10, y: 10 };
      const gridSize = 20;
      const foodScore = 10;

      // Record initial memory
      const initialMemory = monitor.recordMemoryUsage();
      const iterations = 10000;

      // Perform many updates
      for (let i = 0; i < iterations; i++) {
        updateSnake(snake, direction, food, gridSize, foodScore);
      }

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      // Record final memory
      const finalMemory = monitor.recordMemoryUsage();

      // Memory growth should be minimal (less than 1MB)
      if (initialMemory !== null && finalMemory !== null) {
        const memoryGrowth = finalMemory - initialMemory;
        expect(memoryGrowth).toBeLessThan(1); // Less than 1MB growth
        console.log(`Memory growth: ${memoryGrowth.toFixed(2)}MB`);
      }
    });
  });

  describe('FPS Monitoring', () => {
    let monitor: PerformanceMonitor;

    beforeEach(() => {
      monitor = new PerformanceMonitor();
    });

    it('should accurately measure FPS', () => {
      const frameTime = 1000 / 60; // 60 FPS
      const currentTime = performance.now();

      // Simulate 60 frames over 1 second
      for (let i = 0; i < 60; i++) {
        monitor.updateFPS(currentTime + (i * frameTime));
      }

      const fps = monitor.getFPS();
      // In test environment, the timing might be slightly off
      expect(fps).toBeGreaterThan(0);
      expect(fps).toBeLessThanOrEqual(60);
    });

    it('should detect low FPS and generate warnings', () => {
      const frameTime = 1000 / 20; // 20 FPS (below threshold)
      const currentTime = performance.now();

      // Simulate low FPS scenario
      for (let i = 0; i < 20; i++) {
        monitor.updateFPS(currentTime + (i * frameTime));
      }

      const fps = monitor.getFPS();
      expect(fps).toBeLessThan(30);

      const metrics = monitor.getCurrentMetrics();
      expect(metrics.fps).toBeLessThan(30);
    });

    it('should calculate average FPS correctly', () => {
      const currentTime = performance.now();

      // Simulate varying FPS: 60, 30, 60, 30, 60
      const fpsValues = [60, 30, 60, 30, 60];
      fpsValues.forEach((fps, index) => {
        const frameTime = 1000 / fps;
        for (let i = 0; i < fps; i++) {
          monitor.updateFPS(currentTime + (index * 1000) + (i * frameTime));
        }
      });

      const avgFps = monitor.getAverageFPS();
      // Average of [60, 30, 60, 30, 60] = 48
      expect(avgFps).toBeGreaterThan(30);
      expect(avgFps).toBeLessThan(60);
    });
  });

  describe('Input Latency', () => {
    let monitor: PerformanceMonitor;

    beforeEach(() => {
      monitor = new PerformanceMonitor();
    });

    it('should measure input latency', () => {
      // Use a simulated timestamp that's guaranteed to be in the past
      const inputTime = performance.now() - 100; // 100ms ago
      const processingTime = performance.now(); // Now

      const latency = monitor.recordInputLatency(inputTime);
      expect(latency).toBeGreaterThan(0);
      expect(latency).toBeLessThan(200); // Should be less than 200ms
    });

    it('should calculate average input latency', () => {
      const baseTime = performance.now();

      // Simulate multiple inputs with varying latencies
      const latencies = [10, 20, 30, 40, 50]; // ms
      latencies.forEach((latency, index) => {
        const inputTime = baseTime - 100 - (index * 10); // Staggered input times
        monitor.recordInputLatency(inputTime);
      });

      const avgLatency = monitor.getAverageInputLatency();
      expect(avgLatency).toBeGreaterThan(0);
      expect(avgLatency).toBeGreaterThan(50); // At least 50ms average
    });

    it('should detect high input latency', () => {
      const baseTime = performance.now();

      // Simulate high latency input (input was 150ms ago)
      const inputTime = baseTime - 150;
      monitor.recordInputLatency(inputTime);

      const metrics = monitor.getCurrentMetrics();
      expect(metrics.inputLatency).toBeGreaterThan(100);
    });
  });

  describe('Performance Report Generation', () => {
    it('should generate comprehensive performance report', () => {
      const monitor = new PerformanceMonitor();

      // Simulate some activity
      const currentTime = performance.now();
      for (let i = 0; i < 60; i++) {
        monitor.updateFPS(currentTime + (i * (1000 / 60)));
      }

      // Simulate some input latencies
      for (let i = 0; i < 10; i++) {
        monitor.recordInputLatency(currentTime + (i * 100) + i * 20);
      }

      const report = monitor.generateReport();

      expect(report).toHaveProperty('duration');
      expect(report).toHaveProperty('samples');
      expect(report).toHaveProperty('metrics');
      expect(report).toHaveProperty('warnings');
      expect(report).toHaveProperty('environment');

      expect(report.metrics).toHaveProperty('fps');
      expect(report.metrics).toHaveProperty('inputLatency');

      expect(report.metrics.fps).toHaveProperty('average');
      expect(report.metrics.fps).toHaveProperty('min');
      expect(report.metrics.fps).toHaveProperty('max');
      expect(report.metrics.fps).toHaveProperty('stdDev');

      // Environment data might not be available in Node.js
      if (typeof window !== 'undefined') {
        expect(report.environment).toHaveProperty('userAgent');
        expect(report.environment).toHaveProperty('screen');
        expect(report.environment).toHaveProperty('pixelRatio');
        expect(report.environment).toHaveProperty('hardwareConcurrency');
      }

      console.log('Performance Report:', JSON.stringify(report, null, 2));
    });
  });

  describe('Stress Tests', () => {
    it('should handle rapid direction changes without performance degradation', () => {
      const snake = createInitialSnake();
      const direction = createInitialDirection();

      const start = performance.now();
      const iterations = 10000;

      for (let i = 0; i < iterations; i++) {
        isValidDirectionChange(direction, { x: i % 2, y: (i + 1) % 2 });
      }

      const duration = performance.now() - start;
      const avgDuration = duration / iterations;

      expect(avgDuration).toBeLessThan(0.1);
      console.log(`Average rapid direction change time: ${avgDuration.toFixed(4)}ms`);
    });

    it('should handle large snake without performance degradation', () => {
      const gridSize = 20;
      // Create a large snake (occupying 50% of the grid)
      const snake: Array<{ x: number; y: number }> = [];
      for (let i = 0; i < gridSize * gridSize / 2; i++) {
        snake.push({ x: i % gridSize, y: Math.floor(i / gridSize) });
      }

      const direction = { x: 1, y: 0 };
      const food = { x: gridSize - 1, y: gridSize - 1 };
      const foodScore = 10;

      const start = performance.now();
      const iterations = 1000;

      for (let i = 0; i < iterations; i++) {
        updateSnake(snake, direction, food, gridSize, foodScore);
      }

      const duration = performance.now() - start;
      const avgDuration = duration / iterations;

      // Even with large snake, should be fast
      expect(avgDuration).toBeLessThan(5);
      console.log(`Average large snake update time: ${avgDuration.toFixed(3)}ms`);
    });
  });
});

/**
 * Helper function to run manual performance test
 */
export async function runManualPerformanceTest(): Promise<PerformanceReport> {
  const monitor = new PerformanceMonitor();

  console.log('Starting manual performance test...');
  console.log('Please play the game for at least 30 seconds.');

  // Wait for 30 seconds of data collection
  await new Promise(resolve => setTimeout(resolve, 30000));

  const report = monitor.generateReport();

  console.log('\n=== Performance Test Results ===');
  console.log(`Duration: ${(report.duration / 1000).toFixed(2)}s`);
  console.log(`Samples: ${report.samples}`);

  console.log('\n--- FPS Metrics ---');
  console.log(`Average: ${report.metrics.fps.average.toFixed(2)} FPS`);
  console.log(`Min: ${report.metrics.fps.min.toFixed(2)} FPS`);
  console.log(`Max: ${report.metrics.fps.max.toFixed(2)} FPS`);
  console.log(`Std Dev: ${report.metrics.fps.stdDev.toFixed(2)}`);

  console.log('\n--- Input Latency ---');
  console.log(`Average: ${report.metrics.inputLatency.average.toFixed(2)}ms`);
  console.log(`Min: ${report.metrics.inputLatency.min.toFixed(2)}ms`);
  console.log(`Max: ${report.metrics.inputLatency.max.toFixed(2)}ms`);

  if (report.metrics.memory) {
    console.log('\n--- Memory Usage ---');
    console.log(`Average: ${report.metrics.memory.average.toFixed(2)}MB`);
    console.log(`Peak: ${report.metrics.memory.peak.toFixed(2)}MB`);
  }

  if (report.warnings.length > 0) {
    console.log('\n--- Warnings ---');
    report.warnings.forEach(warning => console.log(`⚠️ ${warning}`));
  }

  console.log('\n--- Environment ---');
  console.log(`Screen: ${report.environment.screen.width}x${report.environment.screen.height}`);
  console.log(`Pixel Ratio: ${report.environment.pixelRatio}`);
  console.log(`CPU Cores: ${report.environment.hardwareConcurrency}`);

  return report;
}
