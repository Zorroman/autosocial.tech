import { expect, test } from '@playwright/test';

async function mockDashboardSession(page: any) {
  await page.route('**/api/me', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 1, email: 'qa@autosocial.tech', role: 'admin', plan: 'growth' }),
    });
  });
  await page.route('**/api/plans', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/projects', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 1, name: 'QA Project', created_at: new Date().toISOString(), posts_count: 8 }]),
    });
  });
  await page.route('**/api/posts', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/connections', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 12, provider: 'meta', status: 'connected_ready', page_id: '1', page_name: 'QA Page' }]),
    });
  });
  await page.route('**/api/integrations/youtube/status', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ connected: true, status: 'connected_ready', channel_id: 'yt-1', channel_name: 'QA Channel' }),
    });
  });
  await page.route('**/api/dashboard/summary**', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        reach: 1200,
        views: 1800,
        likes: 77,
        comments: 15,
        shares: 9,
        items: 12,
        engagement_rate: 0.084,
        ai_score: 71.2,
        ai_score_delta_7d: 4.3,
        by_platform: {
          meta: { reach: 750, views: 980, items: 7 },
          youtube: { reach: 450, views: 820, items: 5 },
        },
      }),
    });
  });
  await page.route('**/api/dashboard/ai-score**', async (route: any) => {
    const timeseries = Array.from({ length: 30 }).map((_, i) => ({ day: `2026-02-${String(i + 1).padStart(2, '0')}`, ai_score: 55 + i * 0.6 }));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        current: 71.2,
        delta_7d: 4.3,
        breakdown: {
          performance: { score: 73 },
          consistency: { score: 68 },
          growth: { score: 76 },
          optimization: { score: 64 },
        },
        timeseries,
      }),
    });
  });
  await page.route('**/api/dashboard/timeseries**', async (route: any) => {
    const points = Array.from({ length: 30 }).map((_, i) => ({
      day: `2026-02-${String(i + 1).padStart(2, '0')}`,
      reach: 100 + i * 4,
      views: 160 + i * 5,
      engagement_rate: 0.04 + i * 0.0008,
      meta_reach: 60 + i * 2,
      meta_views: 90 + i * 3,
      youtube_reach: 40 + i * 2,
      youtube_views: 70 + i * 2,
    }));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ points }) });
  });
  await page.route('**/api/dashboard/insights**', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        insights: [
          { impact: 'high', title: 'Лучший день по вовлечению', text: 'Четверг даёт лучший engagement.' },
          { impact: 'medium', title: 'Лучший формат', text: 'Короткий экспертный формат стабильно выигрывает.' },
          { impact: 'low', title: 'Регулярность публикаций', text: 'Добавьте 2 публикации в неделю.' },
          { impact: 'high', title: 'Топ-контент', text: 'Разбор кейса дал максимум реакций.' },
        ],
      }),
    });
  });
  await page.route('**/api/dashboard/recent**', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 100,
            platform: 'meta',
            content_type: 'post',
            title: 'Post A',
            url: 'https://example.com/post-a',
            published_at: new Date().toISOString(),
            engagement_rate: 0.07,
            metrics: { reach: 300, views: 510 },
          },
        ],
      }),
    });
  });
}

test('dashboard loads', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockDashboardSession(page);
  await page.goto('/dashboard');
  await expect(page.getByText('Ваш рост за 30 дней')).toBeVisible();
  await expect(page.getByText('AI-Score / 100')).toBeVisible();
});

test('/api/dashboard/summary returns ok in dashboard flow', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockDashboardSession(page);
  await page.goto('/dashboard');
  const response = await page.waitForResponse((r) => r.url().includes('/api/dashboard/summary'));
  expect(response.status()).toBe(200);
});

test('/api/dashboard/ai-score returns ok in dashboard flow', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'qa-token'));
  await mockDashboardSession(page);
  await page.goto('/dashboard');
  const response = await page.waitForResponse((r) => r.url().includes('/api/dashboard/ai-score'));
  expect(response.status()).toBe(200);
});
