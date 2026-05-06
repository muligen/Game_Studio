/**
 * Performance Monitoring Utility
 * Tracks FPS, input latency, and memory usage
 */

export interface PerformanceMetrics {
  fps: number;
  averageFps: number;
  minFps: number;
  maxFps: number;
  inputLatency: number;
  averageInputLatency: number;
  memoryUsage?: number;
  timestamp: number;
}

export interface PerformanceReport {
  duration: number;
  samples: number;
  metrics: {
    fps: {
      average: number;
      min: number;
      max: number;
      stdDev: number;
    };
    inputLatency: {
      average: number;
      min: number;
      max: number;
      stdDev: number;
    };
    memory?: {
      average: number;
      peak: number;
    };
  };
  warnings: string[];
  environment: {
    userAgent: string;
    screen: { width: number; height: number };
    pixelRatio: number;
    hardwareConcurrency: number;
  };
}

export class PerformanceMonitor {
  private frameCount = 0;
  private lastFpsUpdate = 0;
  private fps = 60;

  private fpsHistory: number[] = [];
  private inputLatencyHistory: number[] = [];
  private memoryHistory: number[] = [];

  private lastInputTime = 0;
  private startTime = 0;
  private isProduction = typeof process !== 'undefined' && process.env?.NODE_ENV === 'production';
  private warningThreshold = 30;

  private warnings: string[] = [];

  constructor() {
    this.startTime = performance.now();
  }

  /**
   * Update FPS counter (should be called every frame)
   */
  updateFPS(currentTime: number): number {
    this.frameCount++;

    // Update FPS every second
    if (currentTime - this.lastFpsUpdate >= 1000) {
      this.fps = this.frameCount;
      this.fpsHistory.push(this.fps);

      // Keep only last 60 seconds of history
      if (this.fpsHistory.length > 60) {
        this.fpsHistory.shift();
      }

      // Check for low FPS warning
      if (this.fps < this.warningThreshold) {
        const warning = `Low FPS detected: ${this.fps}fps at ${new Date().toISOString()}`;
        this.warnings.push(warning);

        if (this.isProduction) {
          console.warn('[Performance Monitor]', warning);
        }
      }

      this.frameCount = 0;
      this.lastFpsUpdate = currentTime;
    }

    return this.fps;
  }

  /**
   * Record input latency
   */
  recordInputLatency(inputTime: number): number {
    const currentTime = performance.now();
    const latency = currentTime - inputTime;

    this.inputLatencyHistory.push(latency);

    // Keep only last 100 samples
    if (this.inputLatencyHistory.length > 100) {
      this.inputLatencyHistory.shift();
    }

    return latency;
  }

  /**
   * Record memory usage (if available)
   */
  recordMemoryUsage(): number | null {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      const usedMB = memory.usedJSHeapSize / (1024 * 1024);

      this.memoryHistory.push(usedMB);

      // Keep only last 60 samples
      if (this.memoryHistory.length > 60) {
        this.memoryHistory.shift();
      }

      return usedMB;
    }
    return null;
  }

  /**
   * Get current FPS
   */
  getFPS(): number {
    return this.fps;
  }

  /**
   * Get average FPS over the recording period
   */
  getAverageFPS(): number {
    if (this.fpsHistory.length === 0) return this.fps;

    const sum = this.fpsHistory.reduce((a, b) => a + b, 0);
    return sum / this.fpsHistory.length;
  }

  /**
   * Get min FPS over the recording period
   */
  getMinFPS(): number {
    if (this.fpsHistory.length === 0) return this.fps;
    return Math.min(...this.fpsHistory);
  }

  /**
   * Get max FPS over the recording period
   */
  getMaxFPS(): number {
    if (this.fpsHistory.length === 0) return this.fps;
    return Math.max(...this.fpsHistory);
  }

  /**
   * Get average input latency
   */
  getAverageInputLatency(): number {
    if (this.inputLatencyHistory.length === 0) return 0;

    const sum = this.inputLatencyHistory.reduce((a, b) => a + b, 0);
    return sum / this.inputLatencyHistory.length;
  }

  /**
   * Calculate standard deviation
   */
  private calculateStdDev(values: number[]): number {
    if (values.length === 0) return 0;

    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const squareDiffs = values.map(value => Math.pow(value - mean, 2));
    const avgSquareDiff = squareDiffs.reduce((a, b) => a + b, 0) / values.length;

    return Math.sqrt(avgSquareDiff);
  }

  /**
   * Get current metrics snapshot
   */
  getCurrentMetrics(): PerformanceMetrics {
    return {
      fps: this.fps,
      averageFps: this.getAverageFPS(),
      minFps: this.getMinFPS(),
      maxFps: this.getMaxFPS(),
      inputLatency: this.getAverageInputLatency(),
      averageInputLatency: this.getAverageInputLatency(),
      memoryUsage: this.memoryHistory.length > 0 ? this.memoryHistory[this.memoryHistory.length - 1] : undefined,
      timestamp: performance.now()
    };
  }

  /**
   * Generate performance report
   */
  generateReport(): PerformanceReport {
    const duration = performance.now() - this.startTime;

    const fpsAvg = this.getAverageFPS();
    const fpsMin = this.getMinFPS();
    const fpsMax = this.getMaxFPS();
    const fpsStdDev = this.calculateStdDev(this.fpsHistory);

    const inputLatencyValues = this.inputLatencyHistory;
    const inputAvg = inputLatencyValues.length > 0
      ? inputLatencyValues.reduce((a, b) => a + b, 0) / inputLatencyValues.length
      : 0;
    const inputMin = inputLatencyValues.length > 0 ? Math.min(...inputLatencyValues) : 0;
    const inputMax = inputLatencyValues.length > 0 ? Math.max(...inputLatencyValues) : 0;
    const inputStdDev = this.calculateStdDev(inputLatencyValues);

    let memoryMetrics;
    if (this.memoryHistory.length > 0) {
      memoryMetrics = {
        average: this.memoryHistory.reduce((a, b) => a + b, 0) / this.memoryHistory.length,
        peak: Math.max(...this.memoryHistory)
      };
    }

    return {
      duration,
      samples: this.fpsHistory.length,
      metrics: {
        fps: {
          average: fpsAvg,
          min: fpsMin,
          max: fpsMax,
          stdDev: fpsStdDev
        },
        inputLatency: {
          average: inputAvg,
          min: inputMin,
          max: inputMax,
          stdDev: inputStdDev
        },
        memory: memoryMetrics
      },
      warnings: [...this.warnings],
      environment: {
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'Node.js',
        screen: typeof window !== 'undefined' ? {
          width: window.screen.width,
          height: window.screen.height
        } : { width: 0, height: 0 },
        pixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
        hardwareConcurrency: typeof navigator !== 'undefined' ? (navigator.hardwareConcurrency || 0) : 0
      }
    };
  }

  /**
   * Reset the monitor
   */
  reset(): void {
    this.frameCount = 0;
    this.lastFpsUpdate = 0;
    this.fps = 60;
    this.fpsHistory = [];
    this.inputLatencyHistory = [];
    this.memoryHistory = [];
    this.startTime = performance.now();
    this.warnings = [];
  }

  /**
   * Check if running in production mode
   */
  isProductionMode(): boolean {
    return this.isProduction;
  }
}

/**
 * Create a singleton instance
 */
export const performanceMonitor = new PerformanceMonitor();

/**
 * Utility function to measure execution time
 */
export function measurePerformance<T>(
  fn: () => T,
  label?: string
): { result: T; duration: number } {
  const start = performance.now();
  const result = fn();
  const duration = performance.now() - start;

  if (label && duration > 16) { // Log if takes more than one frame (60fps = 16.67ms)
    console.warn(`[Performance] ${label} took ${duration.toFixed(2)}ms`);
  }

  return { result, duration };
}
