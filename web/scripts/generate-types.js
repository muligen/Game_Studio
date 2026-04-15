#!/usr/bin/env node
import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Get API base URL from environment variable or use default
const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
const openApiUrl = `${apiBaseUrl}/openapi.json`;
const projectRoot = path.join(__dirname, '..');

console.log(`Generating types from: ${openApiUrl}`);

try {
  // Generate types - use relative path to avoid Windows path issues
  const command = `npx openapi-typescript "${openApiUrl}" -o src/lib/types.ts`;
  execSync(command, {
    stdio: 'inherit',
    cwd: projectRoot,
    shell: true
  });

  console.log('✓ Types generated successfully');

  // Validate TypeScript compilation
  console.log('Validating TypeScript compilation...');
  execSync('tsc --noEmit', {
    stdio: 'inherit',
    cwd: projectRoot
  });

  console.log('✓ TypeScript validation passed');

} catch (error) {
  console.error('✗ Type generation or validation failed');
  process.exit(1);
}
