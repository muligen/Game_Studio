/**
 * Performance Monitor
 *
 * Real-time performance monitoring and FPS validation
 */

export interface PerformanceReport {
  averageFPS: number;
  minFPS: number;
  maxFPS: number;
  frameTimeSamples: number[];
  renderTimeSamples: number[];
  totalTime: number;
  frameCount: number;
  targetFPSMet: boolean;
  efficiency: number;
}

export interface PerformanceThresholds {
  targetFPS: number;
  minAcceptableFPS: number;
  maxFrameTime: number; // in milliseconds
  maxRenderTime: number; // in milliseconds
}

const DEFAULT_THRESHOLDS: PerformanceThresholds = {
  targetFPS: 60,
  minAcceptableFPS: 30,
  maxFrameTime: 33.33, // 30 FPS
  maxRenderTime: 16.67, // 60 FPS
};

/**
 * Performance Monitor Class
 */
export class PerformanceMonitor {
  private thresholds: PerformanceThresholds;
  private fpsSamples: number[];
  private frameTimeSamples: number[];
  private renderTimeSamples: number[];
  private startTime: number;
  private frameCount: number;
  private isMonitoring: boolean;

  constructor(thresholds: Partial<PerformanceThresholds> = {}) {
    this.thresholds = { ...DEFAULT_THRESHOLDS, ...thresholds };
    this.fpsSamples = [];
    this.frameTimeSamples = [];
    this.renderTimeSamples = [];
    this.startTime = 0;
    this.frameCount = 0;
    this.isMonitoring = false;
  }

  /**
   * Start monitoring
   */
  public start(): void {
    this.startTime = performance.now();
    this.isMonitoring = true;
    this.reset();
  }

  /**
   * Stop monitoring
   */
  public stop(): void {
    this.isMonitoring = false;
  }

  /**
   * Reset all samples
   */
  public reset(): void {
    this.fpsSamples = [];
    this.frameTimeSamples = [];
    this.renderTimeSamples = [];
    this.frameCount = 0;
  }

  /**
   * Record a frame sample
   */
  public recordFrame(fps: number, frameTime: number, renderTime: number): void {
    if (!this.isMonitoring) return;

    this.fpsSamples.push(fps);
    this.frameTimeSamples.push(frameTime);
    this.renderTimeSamples.push(renderTime);
    this.frameCount++;
  }

  /**
   * Generate performance report
   */
  public generateReport(): PerformanceReport {
    const totalTime = performance.now() - this.startTime;

    const averageFPS = this.calculateAverage(this.fpsSamples);
    const minFPS = Math.min(...this.fpsSamples, 0);
    const maxFPS = Math.max(...this.fpsSamples, 0);

    const targetFPSMet = averageFPS >= this.thresholds.minAcceptableFPS;

    // Calculate efficiency (ratio of time not spent rendering)
    const avgFrameTime = this.calculateAverage(this.frameTimeSamples);
    const avgRenderTime = this.calculateAverage(this.renderTimeSamples);
    const efficiency = avgFrameTime > 0
      ? Math.max(0, 1 - avgRenderTime / avgFrameTime)
      : 1;

    return {
      averageFPS,
      minFPS,
      maxFPS,
      frameTimeSamples: [...this.frameTimeSamples],
      renderTimeSamples: [...this.renderTimeSamples],
      totalTime,
      frameCount: this.frameCount,
      targetFPSMet,
      efficiency,
    };
  }

  /**
   * Validate performance against thresholds
   */
  public validatePerformance(): {
    passes: boolean;
    issues: string[];
    warnings: string[];
  } {
    const report = this.generateReport();
    const issues: string[] = [];
    const warnings: string[] = [];

    // Check FPS
    if (report.averageFPS < this.thresholds.minAcceptableFPS) {
      issues.push(
        `Average FPS (${report.averageFPS.toFixed(1)}) is below minimum acceptable (${this.thresholds.minAcceptableFPS})`
      );
    } else if (report.averageFPS < this.thresholds.targetFPS * 0.8) {
      warnings.push(
        `Average FPS (${report.averageFPS.toFixed(1)}) is below target (${this.thresholds.targetFPS})`
      );
    }

    // Check frame times
    const avgFrameTime = this.calculateAverage(this.frameTimeSamples);
    if (avgFrameTime > this.thresholds.maxFrameTime) {
      issues.push(
        `Average frame time (${avgFrameTime.toFixed(2)}ms) exceeds maximum (${this.thresholds.maxFrameTime}ms)`
      );
    }

    const maxFrameTime = Math.max(...this.frameTimeSamples, 0);
    if (maxFrameTime > this.thresholds.maxFrameTime * 1.5) {
      warnings.push(
        `Peak frame time (${maxFrameTime.toFixed(2)}ms) detected - may cause stuttering`
      );
    }

    // Check render times
    const avgRenderTime = this.calculateAverage(this.renderTimeSamples);
    if (avgRenderTime > this.thresholds.maxRenderTime) {
      issues.push(
        `Average render time (${avgRenderTime.toFixed(2)}ms) exceeds maximum (${this.thresholds.maxRenderTime}ms)`
      );
    }

    // Check efficiency
    if (report.efficiency < 0.7) {
      warnings.push(
        `Render efficiency (${(report.efficiency * 100).toFixed(1)}%) is low - optimization recommended`
      );
    }

    return {
      passes: issues.length === 0,
      issues,
      warnings,
    };
  }

  /**
   * Get current thresholds
   */
  public getThresholds(): PerformanceThresholds {
    return { ...this.thresholds };
  }

  /**
   * Check if currently monitoring
   */
  public isActive(): boolean {
    return this.isMonitoring;
  }

  /**
   * Get sample count
   */
  public getSampleCount(): number {
    return this.frameCount;
  }

  /**
   * Calculate average of array
   */
  private calculateAverage(values: number[]): number {
    if (values.length === 0) return 0;
    const sum = values.reduce((acc, val) => acc + val, 0);
    return sum / values.length;
  }
}

/**
 * Create a performance monitor
 */
export function createPerformanceMonitor(
  thresholds?: Partial<PerformanceThresholds>
): PerformanceMonitor {
  return new PerformanceMonitor(thresholds);
}

/**
 * Run performance test for specified duration
 */
export async function runPerformanceTest(
  renderCallback: (metrics: { fps: number; frameTime: number; renderTime: number }) => void,
  duration: number = 5000,
  thresholds?: Partial<PerformanceThresholds>
): Promise<PerformanceReport> {
  const monitor = new PerformanceMonitor(thresholds);
  monitor.start();

  const startTime = performance.now();
  let frameCount = 0;
  let lastFrameTime = startTime;

  return new Promise((resolve) => {
    const runFrame = () => {
      const currentTime = performance.now();
      const frameTime = currentTime - lastFrameTime;
      const elapsed = currentTime - startTime;

      if (elapsed >= duration) {
        monitor.stop();
        resolve(monitor.generateReport());
        return;
      }

      // Simulate render callback
      const renderStart = performance.now();
      renderCallback({
        fps: 1000 / frameTime,
        frameTime,
        renderTime: performance.now() - renderStart,
      });

      // Record metrics
      const fps = 1000 / Math.max(frameTime, 1);
      monitor.recordFrame(fps, frameTime, performance.now() - renderStart);

      frameCount++;
      lastFrameTime = currentTime;

      requestAnimationFrame(runFrame);
    };

    runFrame();
  });
}

/**
 * Format performance report for display
 */
export function formatPerformanceReport(report: PerformanceReport): string {
  const lines = [
    'Performance Report',
    '==================',
    `Duration: ${(report.totalTime / 1000).toFixed(2)}s`,
    `Total Frames: ${report.frameCount}`,
    '',
    'FPS Statistics:',
    `  Average: ${report.averageFPS.toFixed(1)} FPS`,
    `  Min: ${report.minFPS.toFixed(1)} FPS`,
    `  Max: ${report.maxFPS.toFixed(1)} FPS`,
    `  Target Met: ${report.targetFPSMet ? '✓' : '✗'}`,
    '',
    'Timing Statistics:',
    `  Avg Frame Time: ${report.frameTimeSamples.length > 0 ? (report.frameTimeSamples.reduce((a, b) => a + b, 0) / report.frameTimeSamples.length).toFixed(2) : 0}ms`,
    `  Avg Render Time: ${report.renderTimeSamples.length > 0 ? (report.renderTimeSamples.reduce((a, b) => a + b, 0) / report.renderTimeSamples.length).toFixed(2) : 0}ms`,
    `  Efficiency: ${(report.efficiency * 100).toFixed(1)}%`,
  ];

  return lines.join('\n');
}
