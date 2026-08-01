# Deployment Checklist (AutoSocial YouTube Factory)

## Перед деплоем (обязательно)
1. `bash scripts/predeploy_check.sh` — останавливается при любой ошибке:
   чистое дерево git, UTF-8/JS syntax/`????`-скан app.js (sha256 в выводе),
   Python syntax, критические тесты, migrations import.
2. Бэкап на сервере: БД + `.env` + `output/` (см. BACKUP_RESTORE.md).
3. Убедиться, что деплой НЕ копирует: `.env`, `output/`, `data/`, `cache/`,
   `generated_media/`, `logs/`, `*.db*` (всё это в .gitignore — деплой из git).

## Production env (fail closed при нарушении)
- `ENV=production` — приложение НЕ стартует без:
  - `ADMIN_ALLOWLIST_EMAILS` (private mode);
  - `TOKEN_ENCRYPTION_KEY`;
  - `COOKIE_SECURE=true`;
  - выключенного debug.
- Critical зависимости (readiness=not_ready без них): база, ffmpeg, ffprobe,
  writable output dir, диск > 1 GB, encryption key, allowlist.
- Optional (readiness=degraded): Redis, RQ worker, OPENAI_API_KEY,
  PEXELS_API_KEY, Google OAuth, edge-tts.

## Порядок деплоя
1. `git pull` нужного commit на сервере (или rsync по git-архиву).
2. `pip install -r requirements.txt` при изменении зависимостей.
3. Рестарт web-сервиса (`python app.py` / gunicorn unit). Миграции additive,
   применяются автоматически при старте.
4. Рестарт worker-сервиса: `python worker.py` (слушает `generation` + `render`).
5. Проверка: `GET /api/health` → 200; `GET /api/readiness` (с admin-токеном)
   → `ready`/`degraded`; страница `/factory-settings/` в UI.

## Диагностика
- **Render job висит в pending**: `GET /api/readiness` → worker offline?
  Redis доступен? `python worker.py` запущен и слушает `render`?
  Логи worker: `logs/worker.log`.
- **Worker offline**: проверить процесс, `redis-cli ping`, REDIS_URL.
- **FFmpeg**: `ffmpeg -version`; путь через `FFMPEG_BIN`.
- **app.js повреждён**: `bash scripts/check_frontend_integrity.sh` — вернёт
  FAIL при `????`/битом UTF-8; восстановить из git.

## Тестовый деплой: команды на сервере (выполнять вручную)
```bash
# 0. Одноразово: убедиться, что серверный .env заполнен (ENV=production,
#    ADMIN_ALLOWLIST_EMAILS, TOKEN_ENCRYPTION_KEY, COOKIE_SECURE=true,
#    OPENAI_API_KEY, REDIS_URL, DATABASE_URL...). .env НЕ копируется с dev.
cd /var/www/api-dev
export APP_DIR=/var/www/api-dev TARGET_COMMIT=<release hash>
export API_URL=https://api-dev.autosocial.tech FRONT_URL=https://dev.autosocial.tech

bash scripts/deploy_test.sh          # backup -> checkout -> deps -> integrity
                                     # -> migrations -> restart web+worker
                                     # -> health -> readiness -> smoke
# при падении:
bash scripts/rollback.sh

# ручная проверка после деплоя:
curl -fsS https://api-dev.autosocial.tech/api/health
SMOKE_EMAIL=<admin> SMOKE_PASSWORD=<pass> \
  python3 scripts/post_deploy_smoke.py --api https://api-dev.autosocial.tech \
  --front https://dev.autosocial.tech
```
Frontend (ADM.tools): каталог `frontend/` раскладывается на dev.autosocial.tech
из того же git-checkout; перед этим обязателен `scripts/check_frontend_integrity.sh`.

## Rollback
`git checkout <предыдущий commit>` + рестарт web и worker. Миграции additive —
старый код работает со свежей схемой. БД восстанавливается из бэкапа только
при порче данных (см. BACKUP_RESTORE.md).

## Cleanup
`python scripts/cleanup_runtime.py` — dry-run (ничего не удаляет);
`--execute` + ввод слова `delete` — реальное удаление. Файлы, привязанные к
сценам/проектам/публикациям/completed-джобам, не удаляются никогда.
