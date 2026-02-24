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
- `DATABASE_URL`
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

Dashboard metrics API:
- `POST /api/dashboard/sync`
- `GET /api/dashboard/summary?days=30`
- `GET /api/dashboard/ai-score?days=30`
- `GET /api/dashboard/forecast?horizon=7&days=90`
- `GET /api/dashboard/timeseries?days=30`
- `GET /api/dashboard/insights?days=30`
- `GET /api/dashboard/recent?limit=10`

Пример ручного запуска синка:
```bash
curl -X POST https://api.autosocial.tech/api/dashboard/sync \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{}"
```

## 5) Smoke tests
```bash
bash tests/smoke/run_smoke.sh
py -m pytest tests/test_dashboard_metrics.py -q
```
Отчет:
- `tests/reports/smoke-YYYYMMDD-HHMMSS.txt`

Проверка AI-Score вручную:
```bash
curl -X GET "http://localhost:5000/api/dashboard/ai-score?days=30" \
  -H "Authorization: Bearer <TOKEN>"
```

Проверка данных в БД:
```sql
SELECT user_id, day, ai_score, performance, consistency, growth, optimization
FROM ai_score_daily
ORDER BY day DESC
LIMIT 30;

SELECT user_id, day, score_total
FROM ai_scores_daily
ORDER BY day DESC
LIMIT 30;

SELECT user_id, horizon_days, based_on_from, based_on_to
FROM forecasts
ORDER BY created_at DESC
LIMIT 10;
```

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

## 9) Create Wizard Flow (/create)
Мастер `/create` работает через сущности кампании:
- `Campaign` (общая идея, текст, режим image/video/both)
- `CampaignAsset` (image/video/thumbnail)
- `CampaignDelivery` (публикация по платформам)
- `GenerationJob` (статус генерации ассетов)

Основные endpoints:
- `POST /api/campaigns`
- `PATCH /api/campaigns/:id`
- `GET /api/campaigns/:id`
- `GET /api/campaigns`
- `POST /api/campaigns/:id/generate-image`
- `POST /api/campaigns/:id/generate-video`
- `GET /api/jobs/:id`
- `POST /api/campaigns/:id/publish`
- `GET /api/deliveries/:id`
- `GET /api/history`

Creator Studio API (текст + AI assist + quality + шаблоны):
- `POST /api/create/suggest` — быстрые варианты (hook/angles/cta)
- `POST /api/create/generate` — генерация draft-вариантов (quick/pro режим)
- `POST /api/create/rewrite` — улучшение существующего текста
- `POST /api/create/quality-check` — score/checks/warnings для текущего поста
- `GET /api/create/templates`
- `POST /api/create/templates`
- `DELETE /api/create/templates/:id`

Стабильность генерации:
- optional JSON-поля больше не валят генерацию
- для strategy/drafts добавлена мягкая нормализация и fallback цепочка
- API возвращает safe payload (`status`, `warnings`, `debug_code`) даже при partial-результате

Локально обязательно запустить backend и frontend, а также worker (для очередей RQ, если включены соответствующие задачи):
```bash
py app.py
py -m http.server 3000 --directory frontend
py worker.py
```

## 10) Docker + миграции
```bash
docker compose up -d --build
```
Миграции выполняются автоматически при старте backend (см. `run_migrations()` в `app.py`).
Для ручного прогона:
```bash
py migrations.py
```

## 11) PRO Video Pipeline
Генерация видео теперь идет локально на сервере через `BASE_DIR`:
- кэш футажей: `cache/footage/`
- артефакты: `output/videos/`, `output/audio/`, `output/subtitles/`, `output/manifests/`

Ключевые ENV:
- `BASE_DIR`
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_TTS_MODEL`
- `OPENAI_TTS_VOICE` (по умолчанию `eddy`)
- `FFMPEG_BIN`
- `FFPROBE_BIN`
- `VIDEO_RENDER_CONCURRENCY`

API:
- `POST /api/video/generate`
- `GET /api/video/jobs/{job_id}`
- `POST /api/video/jobs/{job_id}/publish`

Пример:
```bash
curl -X POST http://localhost:5000/api/video/generate \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "topic":"Как сервису получить больше заявок из контента",
    "offer":"Бесплатный аудит",
    "language":"ru",
    "format":"short",
    "target_seconds":30,
    "orientation":"vertical",
    "style":"expert"
  }'
```

Проверка статуса:
```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:5000/api/video/jobs/<JOB_ID>
```
