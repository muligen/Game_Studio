import { test, expect } from '@playwright/test';

/**
 * React Game Component Browser Compatibility Test Suite
 * Tests the React-based Snake game implementation
 */

test.describe('React Game - Browser Compatibility', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the React app (index.html served by Vite dev server)
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should render React game component', async ({ page }) => {
    const gameContainer = page.locator('.game-container');
    await expect(gameContainer).toBeVisible();
    await expect(gameContainer).toHaveAttribute('role', 'application');
    await expect(gameContainer).toHaveAttribute('aria-label', '贪吃蛇游戏');
  });

  test('should display game header with title and HUD', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('贪吃蛇');
    await expect(page.locator('.scores')).toBeVisible();
    await expect(page.locator('.score-item')).toHaveCount(2);
  });

  test('should show start screen (Menu state)', async ({ page }) => {
    const overlay = page.locator('.overlay');
    await expect(overlay).toBeVisible();
    await expect(overlay).toContainText('贪吃蛇');
    await expect(overlay).toContainText('使用方向键或WASD控制蛇移动');
    await expect(overlay.locator('button')).toContainText('开始游戏');
  });

  test('should start game when clicking start button', async ({ page }) => {
    await page.locator('.overlay button').click();

    // Overlay should be hidden (game starts)
    await expect(page.locator('.overlay')).not.toBeVisible();

    // FPS counter should be visible
    await expect(page.locator('.fps-counter')).toBeVisible();
  });

  test('should respond to keyboard controls', async ({ page }) => {
    // Start the game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(100);

    // Press arrow keys to change direction
    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(50);

    // Game should still be playing
    await expect(page.locator('.overlay')).not.toBeVisible();
  });

  test('should pause game with Escape key', async ({ page }) => {
    // Start the game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(100);

    // Press Escape to pause
    await page.keyboard.press('Escape');
    await expect(page.locator('.overlay')).toBeVisible();
    await expect(page.locator('.pause-text')).toContainText('PAUSED');

    // Resume with button
    await page.locator('.overlay button:has-text("继续游戏")').click();
    await expect(page.locator('.overlay')).not.toBeVisible();
  });

  test('should handle game over and restart', async ({ page }) => {
    // Start the game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(100);

    // Force game over by moving toward wall
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(80);
    }

    // Game over screen should appear
    await expect(page.locator('.overlay')).toBeVisible();
    await expect(page.locator('.overlay')).toContainText('游戏结束');

    // Click restart
    await page.locator('.overlay button:has-text("重新开始")').click();

    // Game should restart
    await page.waitForTimeout(100);
    await expect(page.locator('.score-item').first()).toContainText('0');
  });

  test('should update score during gameplay', async ({ page }) => {
    // Start the game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(100);

    const initialScore = await page.locator('.score-item').first().textContent();

    // Wait for some gameplay
    await page.waitForTimeout(3000);

    const currentScore = await page.locator('.score-item').first().textContent();
    expect(currentScore).toBeDefined();
  });

  test('should display controls information', async ({ page }) => {
    const controlsInfo = page.locator('.controls-info');
    await expect(controlsInfo).toBeVisible();
    await expect(controlsInfo).toContainText('控制:');
    await expect(controlsInfo).toContainText('暂停:');
  });
});

test.describe('React Game - Responsive Design', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should adapt to desktop viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(100);

    const container = page.locator('.game-container');
    await expect(container).toBeVisible();

    const box = await container.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      expect(box.width).toBeGreaterThan(0);
      expect(box.height).toBeGreaterThan(0);
    }
  });

  test('should adapt to tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(100);

    const container = page.locator('.game-container');
    await expect(container).toBeVisible();
  });

  test('should adapt to mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(100);

    const container = page.locator('.game-container');
    await expect(container).toBeVisible();

    // On mobile, controls info should still be visible
    const controlsInfo = page.locator('.controls-info');
    await expect(controlsInfo).toBeVisible();
  });

  test('should resize canvas on window resize', async ({ page }) => {
    // Start with desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(100);

    const canvas = page.locator('canvas');
    const initialBox = await canvas.boundingBox();
    expect(initialBox).toBeTruthy();

    // Resize to mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(100);

    const resizedBox = await canvas.boundingBox();
    expect(resizedBox).toBeTruthy();

    // Canvas should have different size after resize
    if (initialBox && resizedBox) {
      expect(resizedBox.width).toBeLessThan(initialBox.width);
    }
  });
});

test.describe('React Game - Performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should maintain acceptable FPS', async ({ page }) => {
    // Start the game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(500);

    // Collect FPS readings
    const fpsReadings: number[] = [];
    for (let i = 0; i < 5; i++) {
      const fpsText = await page.locator('.fps-counter').textContent();
      const match = fpsText?.match(/FPS:\s*(\d+)/);
      if (match) {
        fpsReadings.push(parseInt(match[1]));
      }
      await page.waitForTimeout(1000);
    }

    if (fpsReadings.length > 0) {
      const avgFps = fpsReadings.reduce((a, b) => a + b, 0) / fpsReadings.length;
      expect(avgFps).toBeGreaterThanOrEqual(30);
      console.log(`Average FPS (React): ${avgFps.toFixed(2)}`);
    }
  });

  test('should respond quickly to input', async ({ page }) => {
    await page.locator('.overlay button').click();
    await page.waitForTimeout(200);

    const startTime = Date.now();
    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(50);

    const responseTime = Date.now() - startTime;
    expect(responseTime).toBeLessThan(100);
  });
});

test.describe('React Game - LocalStorage', () => {
  test('should load and save high score', async ({ page }) => {
    await page.goto('/');

    // Set initial high score
    await page.evaluate(() => {
      localStorage.setItem('snakeHighScore', '50');
    });

    await page.reload();
    await page.waitForLoadState('networkidle');

    // Check high score is displayed
    const highScoreText = await page.locator('.score-item').nth(1).textContent();
    expect(highScoreText).toContain('50');
  });

  test('should update high score after game over', async ({ page }) => {
    await page.goto('/');

    // Clear existing high score
    await page.evaluate(() => {
      localStorage.removeItem('snakeHighScore');
    });

    await page.reload();
    await page.waitForLoadState('networkidle');

    // Verify high score is 0
    const initialHighScore = await page.locator('.score-item').nth(1).textContent();
    expect(initialHighScore).toContain('0');

    // Start game
    await page.locator('.overlay button').click();
    await page.waitForTimeout(100);

    // Force game over
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(80);
    }

    // Wait for game over and check localStorage
    await page.waitForTimeout(500);

    const savedScore = await page.evaluate(() => {
      return localStorage.getItem('snakeHighScore');
    });

    expect(savedScore).toBeTruthy();
  });
});

test.describe('React Game - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should have proper ARIA labels', async ({ page }) => {
    const gameContainer = page.locator('.game-container');
    await expect(gameContainer).toHaveAttribute('role', 'application');
    await expect(gameContainer).toHaveAttribute('aria-label', '贪吃蛇游戏');
  });

  test('should be keyboard accessible', async ({ page }) => {
    // Tab to focus on game
    await page.keyboard.press('Tab');

    // Start game with Enter
    const startButton = page.locator('.overlay button');
    await startButton.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(100);

    // Verify game started
    await expect(page.locator('.overlay')).not.toBeVisible();

    // Control with keyboard
    await page.keyboard.press('ArrowUp');
    await page.keyboard.press('Escape');

    // Should pause
    await expect(page.locator('.overlay')).toBeVisible();
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();
    await expect(h1).toContainText('贪吃蛇');
  });
});
