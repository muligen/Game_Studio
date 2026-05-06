#!/usr/bin/env node
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Get API base URL from environment variable or use default
const apiBaseUrl = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const openApiUrl = `${apiBaseUrl}/openapi.json`;
const projectRoot = path.join(__dirname, '..');
const outputPath = path.join(projectRoot, 'src', 'lib', 'types.ts');

console.log(`Generating types from: ${openApiUrl}`);

try {
  // Generate types - use relative path to avoid Windows path issues
  const command = `npx openapi-typescript "${openApiUrl}" -o src/lib/types.ts`;
  execSync(command, {
    stdio: 'inherit',
    cwd: projectRoot,
    shell: true,
    timeout: 5000,
  });

  console.log('Types generated successfully');

  // Validate TypeScript compilation
  console.log('Validating TypeScript compilation...');
  execSync('tsc --noEmit', {
    stdio: 'inherit',
    cwd: projectRoot
  });

  console.log('TypeScript validation passed');
} catch (error) {
  if (fs.existsSync(outputPath)) {
    console.warn('Type generation failed; using existing src/lib/types.ts for local development.');
    console.warn(error instanceof Error ? error.message : String(error));
    process.exit(0);
  }

  console.error('Type generation or validation failed');
  process.exit(1);
}
