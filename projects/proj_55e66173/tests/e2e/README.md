# Browser Compatibility Testing

This directory contains end-to-end tests for verifying browser compatibility of the Snake game implementation.

## Test Coverage

### Browser Compatibility Tests (`browser-compatibility.spec.ts`)
Tests the standalone HTML demo (`snake-demo.html`) across:

**Browsers:**
- Chrome (Desktop)
- Firefox (Desktop)
- Safari/WebKit (Desktop)
- Edge (Desktop)

**Viewports:**
- Desktop (1920x1080)
- Tablet (768x1024)
- Mobile (375x667, iPhone 13 Pro, Pixel 5)

**Test Areas:**
- Core functionality (start, pause, game over, restart)
- Keyboard controls (Arrow keys, WASD, Esc, P)
- Score tracking and high score persistence
- localStorage support and fallback handling
- Accessibility (ARIA labels, keyboard navigation)
- Canvas 2D rendering
- Performance (FPS ≥ 30, input response ≤ 100ms)

### React Game Tests (`react-game-compatibility.spec.ts`)
Tests the React component implementation:

**Test Areas:**
- Component rendering and state management
- React hooks and useReducer logic
- Responsive canvas resizing
- Game loop and animation frame handling
- LocalStorage integration
- Performance monitoring

### Visual Regression Tests (`visual-regression.spec.ts`)
Screenshot-based tests for visual consistency:

**Test Areas:**
- Start screen layout
- Game over screen
- Pause screen
- Gameplay (snake and food rendering)
- Cross-viewport consistency
- Color and contrast verification

## Prerequisites

Install dependencies:

```bash
npm install --save-dev @playwright/test
```

Install Playwright browsers:

```bash
npx playwright install
```

## Running Tests

### Run all tests
```bash
npm run test:e2e
```

### Run specific test file
```bash
npx playwright test browser-compatibility.spec.ts
```

### Run on specific browser
```bash
npx playwright test --project=chrome-desktop
npx playwright test --project=firefox-desktop
npx playwright test --project=safari-desktop
npx playwright test --project=edge-desktop
```

### Run on specific viewport
```bash
npx playwright test --project=tablet-ipad
npx playwright test --project=mobile-iphone
npx playwright test --project=mobile-android
```

### Run with UI mode
```bash
npx playwright test --ui
```

### Run with debug mode
```bash
npx playwright test --debug
```

### Run visual regression tests
```bash
npx playwright test visual-regression.spec.ts
```

### Update screenshots
```bash
npx playwright test visual-regression.spec.ts --update-snapshots
```

## Test Results

Results are saved in:
- HTML Report: `test-results/results.html`
- JSON Report: `test-results/results.json`
- JUnit Report: `test-results/results.xml`

View HTML report:
```bash
npx playwright show-report
```

## CI/CD Integration

In CI environments, tests run with:
- Automatic retries (2 attempts)
- Parallel execution disabled (single worker)
- Video recording on failure
- Screenshot capture on failure
- Trace files for debugging

## Acceptance Criteria Verification

These tests verify the following acceptance criteria:

1. ✅ Game runs normally in latest Chrome
2. ✅ Game runs normally in latest Firefox
3. ✅ Game runs normally in latest Safari
4. ✅ Game runs normally in latest Edge
5. ✅ Game area displays correctly on desktop screen sizes
6. ✅ Game area adapts correctly on tablet screen sizes
7. ✅ Game area adapts correctly on mobile screen sizes
8. ✅ Compatibility issues are documented

## Performance Benchmarks

Tests verify:
- **FPS**: Average ≥ 30fps during gameplay
- **Input Latency**: Response time ≤ 100ms
- **Memory**: No significant leaks during extended play

## Browser-Specific Notes

### Chrome
- Full feature support
- Best performance
- Recommended primary browser

### Firefox
- Full feature support
- Slightly slower Canvas performance
- All keyboard shortcuts work

### Safari (WebKit)
- Full feature support
- Stricter privacy mode (localStorage may fail)
- Canvas performance varies by device

### Edge
- Based on Chromium
- Same behavior as Chrome
- Full feature support

## Mobile Considerations

- Virtual keyboard not yet supported (MVP is desktop-focused)
- Touch controls planned for v1.1
- Layout adapts to smaller screens
- Performance may vary by device capability

## Troubleshooting

### Tests fail with "Canvas not supported"
- Browser doesn't support Canvas 2D
- Very old browser version

### Tests fail with "localStorage not available"
- Private/Incognito browsing mode
- Browser privacy settings blocking storage
- Expected: game should still function

### Tests timeout
- Dev server not starting: Check `npm run dev` works
- Browser not installed: Run `npx playwright install`
- Port 3000 already in use: Change port in `playwright.config.ts`

### Visual regression failures
- First run: Use `--update-snapshots` to create baseline
- Font differences: Normal across platforms
- Anti-aliasing differences: Use `maxDiffPixels` threshold

## Adding New Tests

1. Create a new `.spec.ts` file in this directory
2. Import Playwright test utilities: `import { test, expect } from '@playwright/test';`
3. Use `test.describe()` to group related tests
4. Use `test.beforeEach()` for common setup
5. Use `await expect()` for assertions
6. Run `npx playwright test` to execute

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Project Acceptance Criteria](../../README.md)
