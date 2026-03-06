# DEPLOY ADM.tools (DEV -> PROD)

> Legacy snapshot only. Active deployment instructions live in the project-root `DEPLOY_ADMTOOLS.md`, and active release assets are the root `frontend/` directory plus root backend files.



## Целевая схема
- PROD FRONT: `https://autosocial.tech`
- PROD API: `https://api.autosocial.tech`
- DEV FRONT: `https://dev.autosocial.tech`
- DEV API: `https://api-dev.autosocial.tech`

## 1) Что сделать в панели ADM.tools

### 1.1 Поддомены
Создайте:
- `api.autosocial.tech`
- `dev.autosocial.tech`
- `api-dev.autosocial.tech`

### 1.2 SSL
Включите Let's Encrypt для:
- `autosocial.tech` (и `www.autosocial.tech`, если используете)
- `api.autosocial.tech`
- `dev.autosocial.tech`
- `api-dev.autosocial.tech`

### 1.3 Front размещение
- `autosocial.tech` -> содержимое `frontend/`
- `dev.autosocial.tech` -> отдельная копия `frontend/` (для staging)

### 1.4 API размещение (Passenger Python)
Разместите две отдельные директории:
- PROD: `/var/www/api`
- DEV: `/var/www/api-dev`

Для каждой:
- Runtime: Python 3.11+
- Startup: `passenger_wsgi.py`
- Root: соответствующая папка

## 2) Файлы на сервере

### 2.1 Backend (в обе папки)
Скопируйте:
- `app.py`, `saas_api.py`, `saas_models.py`, `saas_services.py`, `saas_settings.py`
- `database.py`, `migrations.py`, `stripe_service.py`, `requirements.txt`
- `passenger_wsgi.py`
- остальные backend-модули проекта

### 2.2 Frontend
Скопируйте содержимое папки `frontend/`:
- в root `autosocial.tech`
- в root `dev.autosocial.tech`

## 3) ENV на сервере

### 3.1 PROD `/var/www/api/.env`
```env
FRONTEND_BASE_URL=https://autosocial.tech
API_BASE_URL=https://api.autosocial.tech
META_REDIRECT_URI=https://api.autosocial.tech/api/integrations/meta/callback
FB_LOGIN_REDIRECT_URI=https://api.autosocial.tech/api/auth/oauth/facebook/callback
GOOGLE_REDIRECT_URI=https://api.autosocial.tech/api/auth/oauth/google/callback
FB_APP_ID=9696886733725672
FB_APP_SECRET=...
FB_LOGIN_APP_ID=9696886733725672
FB_LOGIN_APP_SECRET=...
COOKIE_DOMAIN=.autosocial.tech
COOKIE_SECURE=true
CORS_ORIGIN=https://autosocial.tech
ENV=production
MOCK_META=false
USE_MOCK_PROVIDERS=false
TOKEN_ENCRYPTION_KEY=...
OPENAI_API_KEY=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
```

### 3.2 DEV `/var/www/api-dev/.env`
```env
FRONTEND_BASE_URL=https://dev.autosocial.tech
API_BASE_URL=https://api-dev.autosocial.tech
META_REDIRECT_URI=https://api-dev.autosocial.tech/api/integrations/meta/callback
FB_LOGIN_REDIRECT_URI=https://api-dev.autosocial.tech/api/auth/oauth/facebook/callback
GOOGLE_REDIRECT_URI=https://api-dev.autosocial.tech/api/auth/oauth/google/callback
FB_APP_ID=9696886733725672
FB_APP_SECRET=...
FB_LOGIN_APP_ID=9696886733725672
FB_LOGIN_APP_SECRET=...
COOKIE_DOMAIN=.autosocial.tech
COOKIE_SECURE=true
CORS_ORIGIN=https://dev.autosocial.tech
ENV=staging
MOCK_META=true
USE_MOCK_PROVIDERS=true
TOKEN_ENCRYPTION_KEY=...
OPENAI_API_KEY=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
```

## 4) SSH команды (для PROD и DEV отдельно)

```bash
cd /var/www/api            # или /var/www/api-dev
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 migrations.py
python3 seed_admin.py
```

Перезапуск Passenger через панель или touch restart:
```bash
touch tmp/restart.txt
```

## 5) Meta Developers (обязательно)

### App Domains
- `autosocial.tech`
- `api.autosocial.tech`
- `dev.autosocial.tech`
- `api-dev.autosocial.tech`

### Valid OAuth Redirect URIs
PROD:
- `https://api.autosocial.tech/api/auth/oauth/facebook/callback`
- `https://api.autosocial.tech/api/integrations/meta/callback`

DEV:
- `https://api-dev.autosocial.tech/api/auth/oauth/facebook/callback`
- `https://api-dev.autosocial.tech/api/integrations/meta/callback`

### Facebook Login toggles
- Client OAuth Login = ON
- Web OAuth Login = ON

## 6) Проверка после деплоя

### 6.1 Health
```bash
curl -sS https://api-dev.autosocial.tech/health
curl -sS https://api-dev.autosocial.tech/api/health
curl -sS https://api.autosocial.tech/health
curl -sS https://api.autosocial.tech/api/health
```

### 6.2 Smoke
```bash
bash tests/smoke/run_smoke.sh
```
Отчет: `tests/reports/smoke-*.txt`

### 6.3 E2E (DEV)
```bash
cd tests/e2e
npm install
npx playwright install
E2E_BASE_URL=https://dev.autosocial.tech E2E_EXPECTED_META_REDIRECT=https://api-dev.autosocial.tech/api/integrations/meta/callback npm run test:e2e
```
Отчеты:
- `tests/reports/playwright/`
- `tests/artifacts/`

## 7) Диагностика
```bash
tail -n 200 logs/api.log
```

Типичные проблемы:
- `redirect_uri mismatch` -> не совпадают URI в Meta и `.env`.
- `token_exchange_failed` -> неверный `FB_APP_SECRET`.
- `permissions_missing` -> не выданы права Pages/Instagram.
- CORS блокировки -> проверить `CORS_ORIGIN` для prod/dev.

