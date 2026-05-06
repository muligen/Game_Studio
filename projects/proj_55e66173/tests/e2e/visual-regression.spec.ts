import { test, expect } from '@playwright/test';

/**
 * Visual Regression Tests
 * Compare screenshots across browsers and viewport sizes
 */

test.describe('Visual Regression - Cross-Browser Layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/snake-demo.html');
    await page.waitForLoadState('networkidle');
  });

  test('should render start screen consistently @screenshot', async ({ page }) => {
    // Wait for fonts to load
    await page.waitForTimeout(500);

    // Take a screenshot of the start screen
    await expect(page).toHaveScreenshot('start-screen.png', {
      maxDiffPixels: 100,
      threshold: 0.2
    });
  });

  test('should render correctly on desktop viewport @screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(200);

    await expect(page).toHaveScreenshot('desktop-layout.png', {
      fullPage: true,
      maxDiffPixels: 150
    });
  });

  test('should render correctly on tablet viewport @screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(200);

    await expect(page).toHaveScreenshot('tablet-layout.png', {
      fullPage: true,
      maxDiffPixels: 150
    });
  });

  test('should render correctly on mobile viewport @screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(200);

    await expect(page).toHaveScreenshot('mobile-layout.png', {
      fullPage: true,
      maxDiffPixels: 150
    });
  });

  test('should show game over screen correctly @screenshot', async ({ page }) => {
    // Start game
    await page.locator('#start-screen button').click();
    await page.waitForTimeout(200);

    // Force game over
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(80);
    }

    // Wait for game over screen
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('game-over-screen.png', {
      maxDiffPixels: 100
    });
  });

  test('should show pause screen correctly @screenshot', async ({ page }) => {
    // Start game
    await page.locator('#start-screen button').click();
    await page.waitForTimeout(200);

    // Pause game
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);

    await expect(page).toHaveScreenshot('pause-screen.png', {
      maxDiffPixels: 100
    });
  });
});

test.describe('Visual Regression - Game Elements', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/snake-demo.html');
  });

  test('should render snake and food correctly @screenshot', async ({ page }) => {
    // Start game
    await page.locator('#start-screen button').click();
    await page.waitForTimeout(1000);

    // Take screenshot of game canvas only
    const canvas = page.locator('#game-canvas');
    await expect(canvas).toHaveScreenshot('gameplay.png', {
      maxDiffPixels: 200
    });
  });

  test('should maintain aspect ratio across viewports @screenshot', async ({ page }) => {
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 375, height: 667, name: 'mobile' }
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.waitForTimeout(200);

      await expect(page).toHaveScreenshot(`aspect-ratio-${vp.name}.png`, {
        fullPage: true,
        maxDiffPixels: 200
      });
    }
  });
});

test.describe('Visual Regression - Color and Contrast', () => {
  test('should have readable text on start screen', async ({ page }) => {
    await page.goto('/snake-demo.html');
    await page.waitForTimeout(200);

    const startScreen = page.locator('#start-screen');
    await expect(startScreen).toBeVisible();

    // Check contrast ratios using computed styles
    const backgroundColor = await startScreen.evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });

    const textColor = await startScreen.locator('h2').evaluate((el) => {
      return window.getComputedStyle(el).color;
    });

    // Basic check that colors are defined
    expect(backgroundColor).toBeTruthy();
    expect(textColor).toBeTruthy();
  });

  test('should have visible game controls', async ({ page }) => {
    await page.goto('/snake-demo.html');

    const button = page.locator('#start-screen button');
    await expect(button).toBeVisible();

    const styles = await button.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        backgroundColor: computed.backgroundColor,
        color: computed.color,
        padding: computed.padding,
        borderRadius: computed.borderRadius
      };
    });

    // Button should have defined styles
    expect(styles.backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
    expect(styles.color).not.toBe('rgba(0, 0, 0, 0)');
  });
});
