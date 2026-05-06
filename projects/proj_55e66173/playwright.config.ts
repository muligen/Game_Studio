import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for browser compatibility testing
 * Tests Snake game across multiple browsers and viewport sizes
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/results.xml' }]
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    // Desktop browsers - Chrome
    {
      name: 'chrome-desktop',
      use: { ...devices['Desktop Chrome'] },
    },

    // Desktop browsers - Firefox
    {
      name: 'firefox-desktop',
      use: { ...devices['Desktop Firefox'] },
    },

    // Desktop browsers - Safari (WebKit)
    {
      name: 'safari-desktop',
      use: { ...devices['Desktop Safari'] },
    },

    // Desktop browsers - Edge
    {
      name: 'edge-desktop',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'msedge',
      },
    },

    // Tablet - iPad
    {
      name: 'tablet-ipad',
      use: { ...devices['iPad Pro'] },
    },

    // Mobile - iPhone
    {
      name: 'mobile-iphone',
      use: { ...devices['iPhone 13 Pro'] },
    },

    // Mobile - Android
    {
      name: 'mobile-android',
      use: { ...devices['Pixel 5'] },
    },
  ],

  // Run local dev server before starting the tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
