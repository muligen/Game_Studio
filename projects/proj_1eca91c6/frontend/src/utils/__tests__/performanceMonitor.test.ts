/**
 * Performance Monitor Tests
 *
 * Test performance monitoring and FPS validation
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  PerformanceMonitor,
  createPerformanceMonitor,
  runPerformanceTest,
  formatPerformanceReport,
  PerformanceReport,
  PerformanceThresholds,
} from '../performanceMonitor';

describe('PerformanceMonitor', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = createPerformanceMonitor({
      targetFPS: 60,
      minAcceptableFPS: 30,
      maxFrameTime: 33.33,
      maxRenderTime: 16.67,
    });
  });

  afterEach(() => {
    monitor.stop();
  });

  describe('Initialization', () => {
    it('should create monitor with default thresholds', () => {
      const defaultMonitor = createPerformanceMonitor();
      expect(defaultMonitor).toBeDefined();
      defaultMonitor.stop();
    });

    it('should create monitor with custom thresholds', () => {
      const customMonitor = createPerformanceMonitor({
        targetFPS: 120,
        minAcceptableFPS: 60,
      });

      const thresholds = customMonitor.getThresholds();
      expect(thresholds.targetFPS).toBe(120);
      expect(thresholds.minAcceptableFPS).toBe(60);

      customMonitor.stop();
    });

    it('should start in inactive state', () => {
      expect(monitor.isActive()).toBe(false);
    });
  });

  describe('Monitoring Lifecycle', () => {
    it('should start and stop monitoring', () => {
      monitor.start();
      expect(monitor.isActive()).toBe(true);

      monitor.stop();
      expect(monitor.isActive()).toBe(false);
    });

    it('should reset samples', () => {
      monitor.start();
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);

      expect(monitor.getSampleCount()).toBe(2);

      monitor.reset();
      expect(monitor.getSampleCount()).toBe(0);
    });

    it('should restart monitoring after stop', () => {
      monitor.start();
      monitor.recordFrame(60, 16.67, 8);
      monitor.stop();

      monitor.start();
      expect(monitor.getSampleCount()).toBe(0);
    });
  });

  describe('Frame Recording', () => {
    it('should record frame samples', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);

      expect(monitor.getSampleCount()).toBe(3);
    });

    it('should not record when inactive', () => {
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);

      expect(monitor.getSampleCount()).toBe(0);
    });

    it('should handle varying FPS values', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(30, 33.33, 12);
      monitor.recordFrame(120, 8.33, 4);

      expect(monitor.getSampleCount()).toBe(3);
    });
  });

  describe('Performance Reports', () => {
    it('should generate performance report', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);

      const report = monitor.generateReport();

      expect(report.averageFPS).toBe(60);
      expect(report.minFPS).toBe(60);
      expect(report.maxFPS).toBe(60);
      expect(report.frameCount).toBe(3);
      expect(report.totalTime).toBeGreaterThan(0);
    });

    it('should calculate min and max FPS correctly', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(30, 33.33, 12);
      monitor.recordFrame(120, 8.33, 4);

      const report = monitor.generateReport();

      expect(report.averageFPS).toBe(70); // (60 + 30 + 120) / 3
      expect(report.minFPS).toBe(30);
      expect(report.maxFPS).toBe(120);
    });

    it('should calculate efficiency correctly', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8); // 50% efficiency
      monitor.recordFrame(60, 16.67, 8); // 50% efficiency

      const report = monitor.generateReport();
      expect(report.efficiency).toBeCloseTo(0.52, 1);
    });

    it('should handle empty samples', () => {
      monitor.start();

      const report = monitor.generateReport();

      expect(report.averageFPS).toBe(0);
      expect(report.minFPS).toBe(0);
      expect(report.maxFPS).toBe(0);
      expect(report.frameCount).toBe(0);
    });

    it('should copy sample arrays', () => {
      monitor.start();

      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);

      const report1 = monitor.generateReport();
      const report2 = monitor.generateReport();

      // Modifying report1 should not affect report2
      report1.frameTimeSamples.push(100);

      expect(report2.frameTimeSamples.length).toBe(2);
      expect(report1.frameTimeSamples.length).toBe(3);
    });
  });

  describe('Performance Validation', () => {
    it('should pass validation for good performance', () => {
      monitor.start();

      // Record good performance
      for (let i = 0; i < 60; i++) {
        monitor.recordFrame(60, 16.67, 8);
      }

      const validation = monitor.validatePerformance();

      expect(validation.passes).toBe(true);
      expect(validation.issues).toHaveLength(0);
    });

    it('should fail validation for low FPS', () => {
      monitor.start();

      // Record poor performance
      for (let i = 0; i < 60; i++) {
        monitor.recordFrame(20, 50, 25);
      }

      const validation = monitor.validatePerformance();

      expect(validation.passes).toBe(false);
      expect(validation.issues.length).toBeGreaterThan(0);
      expect(validation.issues.some(issue => issue.includes('FPS'))).toBe(true);
    });

    it('should warn about high frame times', () => {
      monitor.start();

      // Record varying performance with some spikes
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(60, 16.67, 8);
      monitor.recordFrame(10, 100, 50); // Spike

      const validation = monitor.validatePerformance();

      expect(validation.warnings.length).toBeGreaterThan(0);
    });

    it('should warn about low efficiency', () => {
      monitor.start();

      // Record low efficiency (high render time)
      for (let i = 0; i < 60; i++) {
        monitor.recordFrame(60, 16.67, 15); // 90% render time
      }

      const validation = monitor.validatePerformance();

      expect(validation.warnings.some(w => w.includes('efficiency'))).toBe(true);
    });

    it('should provide detailed issue descriptions', () => {
      monitor.start();

      monitor.recordFrame(15, 66.67, 33);

      const validation = monitor.validatePerformance();

      expect(validation.issues).toBeDefined();
      expect(Array.isArray(validation.issues)).toBe(true);
    });
  });

  describe('Threshold Management', () => {
    it('should return current thresholds', () => {
      const thresholds = monitor.getThresholds();

      expect(thresholds).toBeDefined();
      expect(thresholds.targetFPS).toBe(60);
      expect(thresholds.minAcceptableFPS).toBe(30);
      expect(thresholds.maxFrameTime).toBe(33.33);
      expect(thresholds.maxRenderTime).toBe(16.67);
    });

    it('should not return original thresholds object', () => {
      const thresholds1 = monitor.getThresholds();
      const thresholds2 = monitor.getThresholds();

      expect(thresholds1).not.toBe(thresholds2);
      expect(thresholds1).toEqual(thresholds2);
    });
  });
});

describe('Performance Test Runner', () => {
  it('should run performance test for specified duration', async () => {
    const renderCallback = vi.fn();

    const report = await runPerformanceTest(renderCallback, 100);

    expect(report).toBeDefined();
    expect(report.totalTime).toBeGreaterThanOrEqual(100);
  });

  it('should record samples during test', async () => {
    const renderCallback = vi.fn();

    const report = await runPerformanceTest(renderCallback, 100);

    expect(report.frameCount).toBeGreaterThan(0);
    expect(report.frameTimeSamples.length).toBeGreaterThan(0);
    expect(report.renderTimeSamples.length).toBeGreaterThan(0);
  });

  it('should use custom thresholds', async () => {
    const renderCallback = vi.fn();

    const report = await runPerformanceTest(
      renderCallback,
      100,
      { targetFPS: 30, minAcceptableFPS: 15 }
    );

    expect(report).toBeDefined();
  });
});

describe('Performance Report Formatting', () => {
  it('should format performance report as string', () => {
    const report: PerformanceReport = {
      averageFPS: 60,
      minFPS: 30,
      maxFPS: 120,
      frameTimeSamples: [16.67, 16.67, 16.67],
      renderTimeSamples: [8, 8, 8],
      totalTime: 5000,
      frameCount: 300,
      targetFPSMet: true,
      efficiency: 0.52,
    };

    const formatted = formatPerformanceReport(report);

    expect(typeof formatted).toBe('string');
    expect(formatted).toContain('Performance Report');
    expect(formatted).toContain('60.0 FPS');
    expect(formatted).toContain('✓');
  });

  it('should handle failed target FPS', () => {
    const report: PerformanceReport = {
      averageFPS: 20,
      minFPS: 15,
      maxFPS: 25,
      frameTimeSamples: [50, 50, 50],
      renderTimeSamples: [25, 25, 25],
      totalTime: 5000,
      frameCount: 100,
      targetFPSMet: false,
      efficiency: 0.5,
    };

    const formatted = formatPerformanceReport(report);

    expect(formatted).toContain('✗');
  });

  it('should handle empty samples', () => {
    const report: PerformanceReport = {
      averageFPS: 0,
      minFPS: 0,
      maxFPS: 0,
      frameTimeSamples: [],
      renderTimeSamples: [],
      totalTime: 0,
      frameCount: 0,
      targetFPSMet: false,
      efficiency: 0,
    };

    const formatted = formatPerformanceReport(report);

    expect(typeof formatted).toBe('string');
    expect(formatted).toContain('0.0 FPS');
  });
});

describe('Performance Monitor Integration', () => {
  it('should work with rendering engine metrics', () => {
    const monitor = createPerformanceMonitor();
    monitor.start();

    // Simulate rendering engine metrics
    const metrics = {
      fps: 60,
      frameTime: 16.67,
      renderTime: 8,
      dirtyRects: 5,
      totalFrames: 100,
    };

    monitor.recordFrame(metrics.fps, metrics.frameTime, metrics.renderTime);

    const report = monitor.generateReport();
    expect(report.averageFPS).toBe(60);
    expect(report.efficiency).toBeCloseTo(0.52, 1);

    monitor.stop();
  });

  it('should track performance over time', () => {
    const monitor = createPerformanceMonitor();
    monitor.start();

    // Simulate performance degradation
    for (let i = 0; i < 10; i++) {
      const fps = 60 - i * 3; // Decreasing FPS
      monitor.recordFrame(fps, 1000 / fps, 10);
    }

    const report = monitor.generateReport();
    expect(report.averageFPS).toBeLessThan(60);
    expect(report.minFPS).toBeLessThan(report.maxFPS);

    monitor.stop();
  });
});
