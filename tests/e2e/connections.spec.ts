import { expect, test } from '@playwright/test';

type Json = Record<string, unknown>;

const MOCK_REDIRECT = process.env.E2E_EXPECTED_META_REDIRECT || 'https://api-dev.autosocial.tech/api/integrations/meta/callback';

async function mockSession(page: any, status: string = 'not_connected') {
  await page.route('**/api/me', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 1, email: 'qa@autosocial.tech', role: 'admin', plan: 'growth' }),
    });
  });

  await page.route('**/api/billing/summary', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        plan: 'growth',
        usage: { posts_per_month: 0, videos_per_month: 0, projects: 1, daily_posts: 0 },
        limits: { posts_per_month: 600, videos_per_month: 40, projects: 5, daily_posts: 60, can_schedule: true, can_autopublish: true, monthly_credits: 1800000, analytics_level: 'advanced' },
        credits_left: 1800000,
        approx_posts_left: 600,
      }),
    });
  });

  const conn: Json = {
    id: 123,
    provider: 'meta',
    status,
    status_reason_code: status === 'connected_need_page' ? 'no_pages' : null,
    status_help_text: status === 'connected_need_page' ? 'Выберите рабочую Facebook Page для публикаций.' : 'Подключите аккаунт.',
    primary_action: status === 'connected_need_page' ? { action: 'pick_page', label: 'Выбрать страницу' } : { action: 'connect', label: 'Подключить Facebook' },
    facebook_page_id: null,
    facebook_page_name: null,
    instagram_business_id: null,
    instagram_username: null,
    meta_redirect_uri: MOCK_REDIRECT,
    tech_log: JSON.stringify({ status, meta_redirect_uri: MOCK_REDIRECT }),
  };

  await page.route('**/api/connections', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([conn]),
    });
  });

  await page.route('**/api/projects', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 1, name: 'QA Project', created_at: new Date().toISOString(), posts_count: 0 }]) });
  });

  await page.route('**/api/posts', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.route('**/api/plans', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.route('**/api/integrations/meta/connect', async (route: any) => {
    const oauthUrl = `https://www.facebook.com/v20.0/dialog/oauth?client_id=9696886733725672&redirect_uri=${encodeURIComponent(MOCK_REDIRECT)}&scope=pages_show_list%2Cpages_read_engagement%2Cinstagram_basic%2Cbusiness_management&state=user_1`;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ oauth_url: oauthUrl, redirect_uri: MOCK_REDIRECT }),
    });
  });

  await page.route('**/api/integrations/meta/pages**', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        pages: [
          { page_id: '111', page_name: 'QA Page 1', page_picture_url: null, ig_user_id: 'ig-111', ig_username: 'qa_ig_1', has_ig: true, already_connected: false },
          { page_id: '222', page_name: 'QA Page 2', page_picture_url: null, ig_user_id: null, ig_username: null, has_ig: false, already_connected: false },
        ],
      }),
    });
  });

  await page.route('**/api/integrations/meta/select-page', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...conn, status: 'connected_ready', facebook_page_id: '111', facebook_page_name: 'QA Page 1', instagram_business_id: 'ig-111', instagram_username: 'qa_ig_1' }),
    });
  });
}

test('A: /connections shows primary connect button', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockSession(page, 'not_connected');
  await page.goto('/connections');

  await expect(page.getByTestId('connect-meta-btn')).toBeVisible();
  await page.screenshot({ path: '../artifacts/connections-a-open.png', fullPage: true });
});

test('B: clicking connect uses oauth URL with api-dev callback', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockSession(page, 'not_connected');
  await page.goto('/connections');

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/api/integrations/meta/connect')),
    page.getByTestId('connect-meta-btn').click(),
  ]);

  expect(request.method()).toBe('POST');
  await page.waitForURL(/facebook\.com\/v20\.0\/dialog\/oauth/);
  expect(page.url()).toContain(encodeURIComponent(MOCK_REDIRECT));
  await page.screenshot({ path: '../artifacts/connections-b-oauth.png', fullPage: true });
});

test('C: page picker modal opens for connected_need_page', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockSession(page, 'connected_need_page');
  await page.goto('/connections');

  await page.getByRole('button', { name: 'Выбрать страницу' }).first().click();
  await expect(page.getByText('Выбор Facebook Page')).toBeVisible();
  await expect(page.getByText('QA Page 1')).toBeVisible();
  await page.screenshot({ path: '../artifacts/connections-c-picker.png', fullPage: true });
});

test('D: details include META_REDIRECT_URI', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockSession(page, 'connected_need_page');
  await page.goto('/connections');

  await page.getByText('Детали').first().click();
  await expect(page.getByTestId('meta-redirect-uri')).toContainText(MOCK_REDIRECT);
  await page.screenshot({ path: '../artifacts/connections-d-details.png', fullPage: true });
});
