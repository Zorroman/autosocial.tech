import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  fullyParallel: false,
  reporter: [
    ['list'],
    ['html', { outputFolder: '../reports/playwright', open: 'never' }],
  ],
  use: {
    // Must be 'localhost', not '127.0.0.1': the backend's CORS_ORIGIN
    // (.env.example) allows http://localhost:3000 specifically, and browsers
    // treat 127.0.0.1 and localhost as different origins even though they
    // resolve to the same box -- using 127.0.0.1 here makes every /api/*
    // fetch from the page fail CORS preflight while curl-style checks (which
    // don't enforce Origin) look fine.
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: '../artifacts',
  // `py` is the Windows-only launcher -- doesn't exist on macOS/Linux (including
  // GitHub Actions' ubuntu-latest runners), so this always failed outside
  // Windows. Fixed to `python3`. Skipped entirely when E2E_BASE_URL points at
  // an already-running stack (e.g. the full Docker Compose stack via Caddy on
  // :80) -- there's nothing for Playwright to spawn or wait on in that case.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        // Bare `http.server` 404s on deep-linked SPA routes (e.g. /operations/,
        // /projects/12) that have no dedicated index.html shell -- this repo's
        // own dev/SPA-fallback server handles that the same way the production
        // edge (Caddy/nginx) does. See scripts/dev_frontend_server.py.
        command: 'python3 ../../scripts/dev_frontend_server.py --port 3000 --root ../../frontend',
        url: 'http://localhost:3000',
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
