/**
 * Compatibility Check Runner
 *
 * This script performs basic compatibility checks without requiring Playwright installation.
 * It validates code patterns and configuration that affect browser compatibility.
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface CompatibilityIssue {
  severity: 'error' | 'warning' | 'info';
  category: string;
  message: string;
  file?: string;
  line?: number;
}

interface CompatibilityReport {
  timestamp: string;
  project: string;
  totalIssues: number;
  bySeverity: Record<string, number>;
  issues: CompatibilityIssue[];
  recommendations: string[];
}

const issues: CompatibilityIssue[] = [];
const recommendations: string[] = [];

// Check 1: CSS Browser Compatibility
function checkCSSCompatibility() {
  const cssFile = join(process.cwd(), 'src', 'Game.css');
  if (existsSync(cssFile)) {
    const content = readFileSync(cssFile, 'utf-8');

    // Check for vendor prefixes
    if (!content.includes('-webkit-') && !content.includes('-moz-') && !content.includes('-ms-')) {
      issues.push({
        severity: 'info',
        category: 'CSS',
        message: 'No vendor prefixes found. Consider using autoprefixer for older browser support.',
        file: cssFile
      });
    }

    // Check for modern CSS features
    if (content.includes('grid') || content.includes('flex')) {
      recommendations.push('CSS Grid and Flexbox are well-supported in modern browsers (Chrome 57+, Firefox 52+, Safari 10.1+, Edge 16+)');
    }
  }
}

// Check 2: JavaScript Browser Compatibility
function checkJSCompatibility() {
  const jsFiles = [
    join(process.cwd(), 'src', 'gameLogic.ts'),
    join(process.cwd(), 'src', 'GameContainer.tsx'),
    join(process.cwd(), 'src', 'GameCanvas.tsx'),
    join(process.cwd(), 'snake-demo.html')
  ];

  const modernFeatures = [
    { feature: 'const/let', description: 'ES6 block-scoped variables' },
    { feature: 'arrow functions', description: 'ES6 arrow functions' },
    { feature: 'template literals', description: 'ES6 template strings' },
    { feature: 'async/await', description: 'ES2017 async functions' },
    { feature: 'optional chaining', description: 'ES2020 optional chaining' },
    { feature: 'nullish coalescing', description: 'ES2020 nullish coalescing' }
  ];

  jsFiles.forEach(file => {
    if (existsSync(file)) {
      const content = readFileSync(file, 'utf-8');

      // Check for modern JavaScript features
      if (content.includes('async ') || content.includes('await ')) {
        issues.push({
          severity: 'info',
          category: 'JavaScript',
          message: 'Uses async/await. Requires polyfill for IE11 or older browsers.',
          file
        });
      }

      if (content.includes('?.')) {
        issues.push({
          severity: 'info',
          category: 'JavaScript',
          message: 'Uses optional chaining (?.). Requires polyfill for older browsers.',
          file
        });
      }

      if (content.includes('??')) {
        issues.push({
          severity: 'info',
          category: 'JavaScript',
          message: 'Uses nullish coalescing operator (??). Requires polyfill for older browsers.',
          file
        });
      }
    }
  });
}

// Check 3: Canvas API Support
function checkCanvasSupport() {
  const demoFile = join(process.cwd(), 'snake-demo.html');
  if (existsSync(demoFile)) {
    const content = readFileSync(demoFile, 'utf-8');

    // Check for canvas fallback
    if (!content.includes('getContext') || !content.includes('Canvas')) {
      issues.push({
        severity: 'error',
        category: 'Canvas',
        message: 'Missing Canvas API support check or fallback.',
        file: demoFile
      });
    }

    // Check for canvas error handling
    if (content.includes('getContext')) {
      recommendations.push('Canvas 2D is supported in all modern browsers (Chrome 1+, Firefox 1.5+, Safari 1+, Edge 12+)');
    }
  }
}

// Check 4: localStorage Support
function checkLocalStorageSupport() {
  const files = [
    join(process.cwd(), 'snake-demo.html'),
    join(process.cwd(), 'src', 'gameLogic.ts')
  ];

  files.forEach(file => {
    if (existsSync(file)) {
      const content = readFileSync(file, 'utf-8');

      // Check for localStorage error handling
      if (content.includes('localStorage') && !content.includes('try') && !content.includes('catch')) {
        issues.push({
          severity: 'warning',
          category: 'localStorage',
          message: 'localStorage usage without try-catch. May fail in private browsing mode.',
          file
        });
      }

      if (content.includes('localStorage')) {
        recommendations.push('localStorage is supported but may be disabled in private browsing mode. Implement fallback handling.');
      }
    }
  });
}

// Check 5: Keyboard Event Codes
function checkKeyboardSupport() {
  const files = [
    join(process.cwd(), 'snake-demo.html'),
    join(process.cwd(), 'src', 'GameContainer.tsx'),
    join(process.cwd(), 'src', 'gameLogic.ts')
  ];

  files.forEach(file => {
    if (existsSync(file)) {
      const content = readFileSync(file, 'utf-8');

      // Check for KeyboardEvent.code usage (modern)
      if (content.includes('e.code') || content.includes('keyCode')) {
        if (content.includes('keyCode')) {
          issues.push({
            severity: 'warning',
            category: 'Keyboard',
            message: 'Uses deprecated keyCode property. Use e.code instead.',
            file
          });
        }
        recommendations.push('KeyboardEvent.code is supported in Chrome 48+, Firefox 38+, Safari 10.1+, Edge 79+');
      }
    }
  });
}

// Check 6: Responsive Design
function checkResponsiveDesign() {
  const cssFile = join(process.cwd(), 'src', 'Game.css');
  const htmlFile = join(process.cwd(), 'snake-demo.html');

  if (existsSync(htmlFile)) {
    const content = readFileSync(htmlFile, 'utf-8');

    // Check for viewport meta tag
    if (!content.includes('viewport')) {
      issues.push({
        severity: 'error',
        category: 'Responsive',
        message: 'Missing viewport meta tag. Mobile layout will be broken.',
        file: htmlFile
      });
    }

    // Check for responsive units
    if (content.includes('vmin') || content.includes('vmax') || content.includes('vw') || content.includes('vh')) {
      recommendations.push('Using viewport units (vw/vh/vmin/vmax) for responsive sizing. Supported in all modern browsers.');
    }
  }
}

// Check 7: Accessibility
function checkAccessibility() {
  const files = [
    join(process.cwd(), 'snake-demo.html'),
    join(process.cwd(), 'src', 'GameContainer.tsx')
  ];

  files.forEach(file => {
    if (existsSync(file)) {
      const content = readFileSync(file, 'utf-8');

      // Check for ARIA labels
      if (!content.includes('aria-label') && !content.includes('aria-labelledby')) {
        issues.push({
          severity: 'warning',
          category: 'Accessibility',
          message: 'Missing ARIA labels. Screen readers may not announce game state correctly.',
          file
        });
      }

      // Check for role attribute
      if (!content.includes('role=')) {
        issues.push({
          severity: 'warning',
          category: 'Accessibility',
          message: 'Missing role attribute. May affect assistive technology.',
          file
        });
      }
    }
  });
}

// Check 8: Performance Considerations
function checkPerformance() {
  const files = [
    join(process.cwd(), 'snake-demo.html'),
    join(process.cwd(), 'src', 'GameContainer.tsx')
  ];

  files.forEach(file => {
    if (existsSync(file)) {
      const content = readFileSync(file, 'utf-8');

      // Check for requestAnimationFrame usage
      if (content.includes('setInterval') || content.includes('setTimeout')) {
        issues.push({
          severity: 'warning',
          category: 'Performance',
          message: 'Using setInterval/setTimeout for animation. Consider requestAnimationFrame for better performance.',
          file
        });
      }

      if (content.includes('requestAnimationFrame')) {
        recommendations.push('requestAnimationFrame provides smoother animations and better battery life.');
      }
    }
  });
}

// Run all checks
function runAllChecks() {
  console.log('🔍 Running Browser Compatibility Checks...\n');

  checkCSSCompatibility();
  checkJSCompatibility();
  checkCanvasSupport();
  checkLocalStorageSupport();
  checkKeyboardSupport();
  checkResponsiveDesign();
  checkAccessibility();
  checkPerformance();
}

// Generate report
function generateReport(): CompatibilityReport {
  const bySeverity: Record<string, number> = {
    error: 0,
    warning: 0,
    info: 0
  };

  issues.forEach(issue => {
    bySeverity[issue.severity]++;
  });

  return {
    timestamp: new Date().toISOString(),
    project: 'Snake Game',
    totalIssues: issues.length,
    bySeverity,
    issues,
    recommendations
  };
}

// Display results
function displayResults(report: CompatibilityReport) {
  console.log('='.repeat(60));
  console.log('📋 Browser Compatibility Report');
  console.log('='.repeat(60));
  console.log(`Project: ${report.project}`);
  console.log(`Timestamp: ${report.timestamp}`);
  console.log(`Total Issues: ${report.totalIssues}`);
  console.log(`  - Errors: ${report.bySeverity.error}`);
  console.log(`  - Warnings: ${report.bySeverity.warning}`);
  console.log(`  - Info: ${report.bySeverity.info}`);
  console.log('='.repeat(60));
  console.log();

  if (report.issues.length > 0) {
    console.log('📌 Issues Found:\n');

    // Group by category
    const grouped = report.issues.reduce((acc, issue) => {
      if (!acc[issue.category]) {
        acc[issue.category] = [];
      }
      acc[issue.category].push(issue);
      return acc;
    }, {} as Record<string, CompatibilityIssue[]>);

    Object.entries(grouped).forEach(([category, items]) => {
      console.log(`\n${category}:`);
      items.forEach(item => {
        const icon = item.severity === 'error' ? '❌' : item.severity === 'warning' ? '⚠️' : 'ℹ️';
        console.log(`  ${icon} ${item.message}`);
        if (item.file) {
          console.log(`     File: ${item.file.split('\\').pop()}`);
        }
      });
    });
    console.log();
  }

  if (report.recommendations.length > 0) {
    console.log('💡 Recommendations:\n');
    report.recommendations.forEach(rec => {
      console.log(`  • ${rec}`);
    });
    console.log();
  }

  // Overall assessment
  console.log('='.repeat(60));
  if (report.bySeverity.error === 0 && report.bySeverity.warning === 0) {
    console.log('✅ PASS: No critical compatibility issues found!');
    console.log('   The code is ready for comprehensive browser testing.');
  } else if (report.bySeverity.error === 0) {
    console.log('⚠️  WARNING: Minor issues found that should be addressed.');
    console.log('   The code is functional but could be improved.');
  } else {
    console.log('❌ FAIL: Critical issues found that must be fixed.');
    console.log('   Please address the errors before comprehensive testing.');
  }
  console.log('='.repeat(60));

  // Browser support summary
  console.log('\n🌐 Expected Browser Support:\n');
  console.log('  ✅ Chrome/Edge: Full support (recommended)');
  console.log('  ✅ Firefox: Full support');
  console.log('  ✅ Safari: Full support (may have localStorage issues in private mode)');
  console.log('  ⚠️  IE11: Not supported (ES6+ features, Canvas, no polyfills)');
  console.log();
}

// Save report to file
function saveReport(report: CompatibilityReport) {
  const reportDir = join(process.cwd(), 'test-results');
  const fs = require('fs');

  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }

  const reportPath = join(reportDir, 'compatibility-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\n📄 Report saved to: ${reportPath}`);
}

// Main execution
try {
  runAllChecks();
  const report = generateReport();
  displayResults(report);
  saveReport(report);

  // Exit with appropriate code
  process.exit(report.bySeverity.error > 0 ? 1 : 0);
} catch (error) {
  console.error('Error running compatibility checks:', error);
  process.exit(1);
}
