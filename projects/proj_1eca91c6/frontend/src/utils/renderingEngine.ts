/**
 * Rendering Engine
 *
 * High-performance canvas rendering engine with FPS tracking,
 * dirty rectangle optimization, and batch rendering
 */

export interface RenderPerformanceMetrics {
  fps: number;
  frameTime: number;
  renderTime: number;
  dirtyRects: number;
  totalFrames: number;
}

export interface DirtyRectangle {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RenderingEngineConfig {
  targetFPS: number;
  enableDirtyRectangles: boolean;
  enablePerformanceMetrics: boolean;
  debugMode: boolean;
}

const DEFAULT_CONFIG: RenderingEngineConfig = {
  targetFPS: 60,
  enableDirtyRectangles: true,
  enablePerformanceMetrics: true,
  debugMode: false,
};

/**
 * Rendering Engine Class
 * Handles optimized canvas rendering with performance tracking
 */
export class RenderingEngine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private config: RenderingEngineConfig;
  private metrics: RenderPerformanceMetrics;
  private dirtyRectangles: Set<string>;
  private previousFrameTime: number;
  private frameCount: number;
  private fpsUpdateTime: number;
  private currentFPS: number;
  private animationFrameId: number | null;
  private lastRenderData: Map<string, any>;

  constructor(canvas: HTMLCanvasElement, config: Partial<RenderingEngineConfig> = {}) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) {
      throw new Error('Failed to get 2D context from canvas');
    }
    this.ctx = ctx;
    this.config = { ...DEFAULT_CONFIG, ...config };

    this.metrics = {
      fps: 0,
      frameTime: 0,
      renderTime: 0,
      dirtyRects: 0,
      totalFrames: 0,
    };

    this.dirtyRectangles = new Set();
    this.previousFrameTime = performance.now();
    this.frameCount = 0;
    this.fpsUpdateTime = 0;
    this.currentFPS = 0;
    this.animationFrameId = null;
    this.lastRenderData = new Map();
  }

  /**
   * Get current performance metrics
   */
  public getMetrics(): RenderPerformanceMetrics {
    return { ...this.metrics };
  }

  /**
   * Mark a region as dirty (needs redrawing)
   */
  public markDirty(x: number, y: number, width: number, height: number): void {
    if (!this.config.enableDirtyRectangles) {
      return;
    }

    const key = `${Math.floor(x)},${Math.floor(y)},${Math.floor(width)},${Math.floor(height)}`;
    this.dirtyRectangles.add(key);
  }

  /**
   * Mark entire canvas as dirty
   */
  public markAllDirty(): void {
    this.dirtyRectangles.clear();
    this.dirtyRectangles.add('full');
  }

  /**
   * Clear specified rectangle
   */
  private clearRect(x: number, y: number, width: number, height: number): void {
    this.ctx.clearRect(x, y, width, height);
  }

  /**
   * Clear all dirty rectangles
   */
  private clearDirtyRectangles(): void {
    if (!this.config.enableDirtyRectangles || this.dirtyRectangles.has('full')) {
      // Clear entire canvas
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this.dirtyRectangles.clear();
      this.metrics.dirtyRects = 1;
      return;
    }

    // Clear only dirty rectangles
    this.metrics.dirtyRects = this.dirtyRectangles.size;
    this.dirtyRectangles.forEach(key => {
      const [x, y, width, height] = key.split(',').map(Number);
      this.clearRect(x, y, width, height);
    });
    this.dirtyRectangles.clear();
  }

  /**
   * Start render frame
   */
  public beginFrame(): void {
    const now = performance.now();
    this.metrics.frameTime = now - this.previousFrameTime;
    this.previousFrameTime = now;

    // Calculate FPS
    this.frameCount++;
    this.fpsUpdateTime += this.metrics.frameTime;

    if (this.fpsUpdateTime >= 1000) {
      this.currentFPS = Math.round((this.frameCount * 1000) / this.fpsUpdateTime);
      this.metrics.fps = this.currentFPS;
      this.frameCount = 0;
      this.fpsUpdateTime = 0;
    }

    // Clear dirty rectangles
    this.clearDirtyRectangles();
  }

  /**
   * End render frame
   */
  public endFrame(): void {
    this.metrics.totalFrames++;
    const now = performance.now();
    this.metrics.renderTime = now - this.previousFrameTime;

    if (this.config.debugMode) {
      this.drawDebugInfo();
    }
  }

  /**
   * Draw debug information
   */
  private drawDebugInfo(): void {
    const fontSize = 12;
    this.ctx.font = `${fontSize}px monospace`;
    this.ctx.fillStyle = '#00FF00';
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';

    const lines = [
      `FPS: ${this.metrics.fps}`,
      `Frame Time: ${this.metrics.frameTime.toFixed(2)}ms`,
      `Render Time: ${this.metrics.renderTime.toFixed(2)}ms`,
      `Dirty Rects: ${this.metrics.dirtyRects}`,
      `Total Frames: ${this.metrics.totalFrames}`,
    ];

    let y = 10;
    lines.forEach(line => {
      this.ctx.fillText(line, 10, y);
      y += fontSize + 4;
    });
  }

  /**
   * Draw a rectangle with batch rendering
   */
  public drawRect(
    x: number,
    y: number,
    width: number,
    height: number,
    fillColor: string,
    strokeColor?: string,
    lineWidth: number = 1
  ): void {
    this.ctx.fillStyle = fillColor;
    this.ctx.fillRect(x, y, width, height);

    if (strokeColor) {
      this.ctx.strokeStyle = strokeColor;
      this.ctx.lineWidth = lineWidth;
      this.ctx.strokeRect(x, y, width, height);
    }

    if (this.config.enableDirtyRectangles) {
      this.markDirty(x, y, width, height);
    }
  }

  /**
   * Draw a circle with batch rendering
   */
  public drawCircle(
    centerX: number,
    centerY: number,
    radius: number,
    fillColor: string,
    strokeColor?: string,
    lineWidth: number = 1
  ): void {
    this.ctx.beginPath();
    this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    this.ctx.fillStyle = fillColor;
    this.ctx.fill();

    if (strokeColor) {
      this.ctx.strokeStyle = strokeColor;
      this.ctx.lineWidth = lineWidth;
      this.ctx.stroke();
    }

    if (this.config.enableDirtyRectangles) {
      this.markDirty(
        centerX - radius - 2,
        centerY - radius - 2,
        radius * 2 + 4,
        radius * 2 + 4
      );
    }
  }

  /**
   * Draw text
   */
  public drawText(
    text: string,
    x: number,
    y: number,
    fillColor: string,
    fontSize: number = 12,
    fontFamily: string = 'monospace'
  ): void {
    this.ctx.font = `${fontSize}px ${fontFamily}`;
    this.ctx.fillStyle = fillColor;
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';
    this.ctx.fillText(text, x, y);

    if (this.config.enableDirtyRectangles) {
      const metrics = this.ctx.measureText(text);
      this.markDirty(x, y, metrics.width, fontSize);
    }
  }

  /**
   * Start animation loop
   */
  public startAnimation(callback: () => void): void {
    if (this.animationFrameId !== null) {
      return; // Already running
    }

    const animate = () => {
      this.beginFrame();
      callback();
      this.endFrame();

      this.animationFrameId = requestAnimationFrame(animate);
    };

    this.animationFrameId = requestAnimationFrame(animate);
  }

  /**
   * Stop animation loop
   */
  public stopAnimation(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  /**
   * Reset metrics
   */
  public resetMetrics(): void {
    this.metrics = {
      fps: 0,
      frameTime: 0,
      renderTime: 0,
      dirtyRects: 0,
      totalFrames: 0,
    };
    this.frameCount = 0;
    this.fpsUpdateTime = 0;
    this.currentFPS = 0;
  }

  /**
   * Check if target FPS is being met
   */
  public isTargetFPSMet(): boolean {
    return this.metrics.fps >= this.config.targetFPS;
  }

  /**
   * Get canvas context
   */
  public getContext(): CanvasRenderingContext2D {
    return this.ctx;
  }

  /**
   * Get canvas
   */
  public getCanvas(): HTMLCanvasElement {
    return this.canvas;
  }

  /**
   * Destroy rendering engine
   */
  public destroy(): void {
    this.stopAnimation();
    this.lastRenderData.clear();
    this.dirtyRectangles.clear();
  }
}

/**
 * Create a rendering engine instance
 */
export function createRenderingEngine(
  canvas: HTMLCanvasElement,
  config?: Partial<RenderingEngineConfig>
): RenderingEngine {
  return new RenderingEngine(canvas, config);
}

/**
 * Validate FPS meets minimum requirement
 */
export function validateFPS(metrics: RenderPerformanceMetrics, minFPS: number = 30): boolean {
  return metrics.fps >= minFPS;
}

/**
 * Calculate render efficiency (ratio of render time to frame time)
 */
export function calculateRenderEfficiency(metrics: RenderPerformanceMetrics): number {
  if (metrics.frameTime === 0) return 1;
  return Math.max(0, Math.min(1, 1 - metrics.renderTime / metrics.frameTime));
}
