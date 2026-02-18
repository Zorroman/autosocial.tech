# AutoSocial GPT SaaS

## 1) Локальный запуск
```bash
copy .env.example .env
py -m pip install -r requirements.txt
py migrations.py
py seed_admin.py
py app.py
py -m http.server 3000 --directory frontend
```

- Front: `http://localhost:3000/login/`
- API: `http://localhost:5000/health`
- API (namespace): `http://localhost:5000/api/health`

## 2) ENV (ключевые переменные)
Используйте `.env.example`.

Критичные для OAuth/хостинга:
- `FRONTEND_BASE_URL`
- `API_BASE_URL`
- `CORS_ORIGIN`
- `COOKIE_DOMAIN`
- `COOKIE_SECURE`
- `META_REDIRECT_URI`
- `FB_LOGIN_REDIRECT_URI`
- `GOOGLE_REDIRECT_URI`
- `FB_APP_ID`
- `FB_APP_SECRET`
- `FB_LOGIN_APP_ID`
- `FB_LOGIN_APP_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `MOCK_META`

## 3) Auth setup (Google + Facebook)
Google Cloud Console:
- Authorized redirect URI:
  - `https://api.autosocial.tech/api/auth/oauth/google/callback`
  - `https://api-dev.autosocial.tech/api/auth/oauth/google/callback`

Meta Developers:
- App Domains:
  - `autosocial.tech`
  - `api.autosocial.tech`
  - `dev.autosocial.tech`
  - `api-dev.autosocial.tech`
- Valid OAuth Redirect URIs:
  - `https://api.autosocial.tech/api/auth/oauth/facebook/callback`
  - `https://api.autosocial.tech/api/integrations/meta/callback`
  - `https://api-dev.autosocial.tech/api/auth/oauth/facebook/callback`
  - `https://api-dev.autosocial.tech/api/integrations/meta/callback`
- Facebook Login:
  - Client OAuth Login = ON
  - Web OAuth Login = ON

## 4) Основные API
- `GET /health`
- `GET /api/health`
- `POST /api/integrations/meta/connect`
- `GET /api/integrations/meta/callback`
- `GET /api/integrations/meta/pages`
- `POST /api/integrations/meta/select-page`
- `POST /api/integrations/meta/test-post`
- `POST /api/integrations/meta/refresh`
- `POST /api/integrations/meta/disconnect`

## 5) Smoke tests
```bash
bash tests/smoke/run_smoke.sh
```
Отчет:
- `tests/reports/smoke-YYYYMMDD-HHMMSS.txt`

## 6) E2E tests (Playwright)
```bash
cd tests/e2e
npm install
set E2E_BASE_URL=https://dev.autosocial.tech
set E2E_EXPECTED_META_REDIRECT=https://api-dev.autosocial.tech/api/integrations/meta/callback
npx playwright install
npm run test:e2e
```
Артефакты:
- Скриншоты/trace/video: `tests/artifacts/`
- HTML report: `tests/reports/playwright/`

## 7) QA checklist (/connections)
1. Статус `not_connected` -> primary `Подключить Facebook`.
2. `connected_need_page` -> primary `Выбрать страницу`.
3. `connected_ready` -> primary `Тест публикации`.
4. `token_expired`/`permissions_missing`/`disconnected` -> primary `Переподключить`.
5. В `Детали` видны:
   - `status_reason_code`
   - `META_REDIRECT_URI`
   - `last_success_at`
   - кнопка `Скопировать тех.лог`.

## 8) Логи
- API лог пишет в `logs/api.log`
- Проверка последних записей:
```bash
tail -n 200 logs/api.log
```
