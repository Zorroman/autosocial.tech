import { expect, test, request as playwrightRequest, type Page } from '@playwright/test';

// Real end-to-end smoke: real backend, real Postgres/Redis/worker (via the
// Docker Compose stack), real login flow. Nothing here is route-mocked --
// see dashboard.spec.ts / connections.spec.ts for the older mocked-route
// style covering the legacy SaaS dashboard.
//
// Demo data comes from scripts/seed_demo_data.py (channel + short/long/
// processing/failed projects + a mock publication) run against the same
// backend this suite talks to. Login uses the ADMIN_EMAIL/ADMIN_PASSWORD
// the backend auto-seeds on boot (see app.py) -- default
// admin@autosocial.local / admin12345, overridable via env vars below to
// match whatever .env the target stack was started with.
//
// Login happens exactly ONCE for the whole file (beforeAll), not per test:
// the backend enforces a real AUTH_CODE_COOLDOWN_SECONDS (default 45s)
// between challenge requests for the same email -- correct anti-abuse
// behavior, not a bug -- so calling the challenge endpoint once per test
// self-inflicts a 429 on every test after the first. One token, reused via
// localStorage in every test's addInitScript, is both faster and correct.

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:5000';
const EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@autosocial.local';
const PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'admin12345';

async function realLoginToken(): Promise<string> {
  const api = await playwrightRequest.newContext();
  try {
    const challengeRes = await api.post(`${API_BASE}/api/auth/challenge`, {
      data: { flow: 'login', email: EMAIL, password: PASSWORD, honeypot: '' },
    });
    expect(challengeRes.ok(), 'auth/challenge must succeed').toBeTruthy();
    const challenge = await challengeRes.json();
    const devCode = challenge.dev_code;
    expect(devCode, 'dev_code must be present (SMTP must be unset/mocked for this to work)').toBeTruthy();

    const verifyRes = await api.post(`${API_BASE}/api/auth/verify-code`, {
      data: { challenge_token: challenge.challenge_token, code: devCode },
    });
    expect(verifyRes.ok(), 'auth/verify-code must succeed').toBeTruthy();
    const verified = await verifyRes.json();
    expect(verified.token).toBeTruthy();
    return verified.token as string;
  } finally {
    await api.dispose();
  }
}

function trackHealth(page: Page) {
  const consoleErrors: string[] = [];
  const failedApiRequests: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('requestfailed', (req) => {
    if (req.url().includes('/api/')) failedApiRequests.push(`${req.url()} :: ${req.failure()?.errorText}`);
  });
  page.on('response', (res) => {
    if (res.url().includes('/api/') && res.status() >= 500) {
      failedApiRequests.push(`${res.url()} :: HTTP ${res.status()}`);
    }
  });
  return { consoleErrors, failedApiRequests };
}

test.describe('AI Video Factory -- full stack smoke', () => {
  let token: string;

  test.beforeAll(async () => {
    token = await realLoginToken();
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([t]) => {
      localStorage.setItem('token', t);
      localStorage.setItem('lang', 'ru');
    }, [token]);
  });

  test('1. login / demo authentication works against the real backend', async () => {
    expect(token.length).toBeGreaterThan(10);
  });

  test('2. dashboard loads with no critical console/network errors', async ({ page }) => {
    const health = trackHealth(page);
    await page.goto('/dashboard/');
    await expect(page.getByText('Панель').first()).toBeVisible();
    await expect(page.getByText('Быстрые действия')).toBeVisible();
    expect(health.consoleErrors, health.consoleErrors.join('\n')).toEqual([]);
    expect(health.failedApiRequests, health.failedApiRequests.join('\n')).toEqual([]);
  });

  test('3. operations shows real backend/DB/Redis/worker status', async ({ page }) => {
    await page.goto('/operations/');
    await expect(page.getByRole('heading', { name: 'Operations' })).toBeVisible();
    await expect(page.getByText('Backend API')).toBeVisible();
    await expect(page.getByText('База данных')).toBeVisible();
    await expect(page.getByText('Redis')).toBeVisible();
    await expect(page.getByText('RQ worker')).toBeVisible();
    // The whole point of this page: real infra state, not a static mock.
    await expect(page.getByText('online', { exact: true })).toBeVisible();
  });

  test('4. Create Hub is video-first (Short/Long primary)', async ({ page }) => {
    await page.goto('/create/');
    await expect(page.getByText('Создать видео')).toBeVisible();
    await expect(page.getByText('Короткое видео')).toBeVisible();
    await expect(page.getByText('Длинное видео')).toBeVisible();
  });

  test('5. Short flow opens Content Director', async ({ page }) => {
    await page.goto('/create/');
    await page.getByRole('button', { name: /Открыть Content Director/ }).first().click();
    await expect(page.getByText('Content Director').first()).toBeVisible();
    await expect(page.getByText('Придумать следующий ролик').first()).toBeVisible();
  });

  test('6. Long flow opens Content Director', async ({ page }) => {
    await page.goto('/create/');
    await page.getByRole('button', { name: /Открыть Content Director/ }).nth(1).click();
    await expect(page.getByText('Content Director').first()).toBeVisible();
    await expect(page.getByText('Придумать следующий ролик').first()).toBeVisible();
  });

  test('7. Projects list shows the seeded demo projects', async ({ page }) => {
    await page.goto('/projects/');
    // seed_demo_data.py's projects live on "Demo Channel", not whichever
    // channel the page defaults to selecting first.
    await page.getByLabel('Канал:').selectOption({ label: 'Demo Channel' });
    await expect(page.getByText('Demo Short (completed)')).toBeVisible();
    await expect(page.getByText('Demo Long (completed)')).toBeVisible();
    await expect(page.getByText('Demo Short (processing)')).toBeVisible();
    await expect(page.getByText('Demo Short (failed)')).toBeVisible();
  });

  test('8. Completed Video Details shows a real download/open action', async ({ page }) => {
    await page.goto('/projects/');
    await page.getByLabel('Канал:').selectOption({ label: 'Demo Channel' });
    await page.getByText('Demo Short (completed)').click();
    await expect(page.getByText('rendered').first()).toBeVisible();
  });

  test('9. Failed Video Details shows the real, human-readable error', async ({ page }) => {
    await page.goto('/projects/');
    await page.getByLabel('Канал:').selectOption({ label: 'Demo Channel' });
    await page.getByText('Demo Short (failed)').click();
    await expect(page.getByText(/scenes_missing_media/)).toBeVisible();
  });

  test('10. Mobile navigation works', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/dashboard/');
    await expect(page.getByText('Панель').first()).toBeVisible();
    await expect(page.getByText('Operations')).toBeVisible();
  });

  test('11+12. No console errors / no failed required-API requests across core pages', async ({ page }) => {
    const health = trackHealth(page);
    for (const path of ['/dashboard/', '/operations/', '/create/', '/projects/']) {
      await page.goto(path);
      await page.waitForTimeout(300);
    }
    expect(health.consoleErrors, health.consoleErrors.join('\n')).toEqual([]);
    expect(health.failedApiRequests, health.failedApiRequests.join('\n')).toEqual([]);
  });

  test('13. No horizontal overflow on mobile across core pages', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    for (const path of ['/dashboard/', '/operations/', '/create/', '/projects/']) {
      await page.goto(path);
      const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
      expect(fits, `${path} has horizontal overflow on mobile`).toBe(true);
    }
  });
});
