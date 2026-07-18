# Release Readiness — AutoSocial YouTube Factory

Дата аудита: 2026-07-18. Локальный release audit; deployment не выполнялся.

## Release commits
| Commit | Содержимое |
|---|---|
| `28b135e` | factory dashboard, readiness, production validation, cleanup, predeploy gate |
| `5ea860f` | channel analytics + AI cost tracking + budgets |
| `9c0e7a0` | YouTube publication workflow (manual-first + auto-upload код) |
| `cf190a8` | реальный TTS (edge) + Pexels stock media |
| `650b33e` | private mode, Channels, VideoProject/сцены, render queue, реальный MP4 |

Ветка `main`, 5 commits впереди origin/main. Push не выполнялся.

## Функционал релиза
Закрытый private-admin режим (fail closed) · каналы (до 10) с идеями (AI при
квоте OpenAI) · видео-проекты: сценарий → сцены → медиа (Pexels/фикстуры) →
TTS (edge бесплатно / OpenAI) → субтитры → FFmpeg-рендер 1080×1920 →
превью/скачивание · очередь RQ+Redis с реальным прогрессом/retry/cancel ·
публикации manual-first (+код автозагрузки) · аналитика manual + Data API
sync (mocked) · AI cost tracking с бюджетами · factory dashboard · readiness
· cleanup dry-run · predeploy gate.

## Тесты (полный suite)
- **127 passed, 11 failed, 1 skipped** (`pytest tests/ --ignore=tests/e2e`).
- Все 55 тестов нового factory-флоу зелёные (private_admin 10, video_projects 5,
  publications 8, analytics_costs 11, factory_dashboard 7, render_fixture 1 +
  зелёная часть legacy).
- 11 падений — **pre-existing legacy** (проверено git-stash базлайном до
  изменений): `test_ai_director` (1), `test_content_generation` (1),
  `test_media_query_builder` (1), `test_pexels_service` (1),
  `test_video_pipeline::test_ai_video_render_and_status_shape` (1),
  `test_saas_conversion_ui` (6 — проверяют старый SaaS first-run dashboard,
  замещённый factory dashboard). Ни один не затрагивает factory flow.

## Predeploy gate
`scripts/predeploy_check.sh` → **ALL PRE-DEPLOY CHECKS PASSED**
(git clean, UTF-8/JS/`????` app.js + sha256, python syntax, критические тесты
включая factory dashboard/readiness/cleanup, `git diff --check`, migrations).
Полный legacy-suite сознательно не входит в gate (11 известных legacy-падений)
и остаётся отдельной audit-проверкой.

## E2E evidence (локально, без платных запросов)
Браузер: dashboard (реальные метрики) → канал «Эзотерика» (настройки+YouTube
блок) → проект 2 (3 сцены, voiceover file-mode 18.36s edge-TTS, Pexels-метаданные
vertical) → публикация #1 (manual published) → аналитика (manual 450 views)
→ Система (readiness ready, 13 проверок). Свежий рендер через реальную
RQ-очередь: job 4 → `data/output/videos/project_1_job_4.mp4`, ffprobe: h264
1080×1920 yuv420p, aac, 12.4 s; download 200. Джоб пережил падение worker
(Redis-таймаут) и был выполнен после рестарта — очередь с Redis durable.

## Production validation (фиктивные env, реальный .env не изменялся)
- без allowlist → BLOCKED (fail closed) ✅
- без TOKEN_ENCRYPTION_KEY → BLOCKED ✅
- COOKIE_SECURE=false → BLOCKED ✅
- корректная конфигурация → STARTED ✅
- debug: Flask debug по умолчанию выключен; проверяется в validation.

## Security scan
Последние 5 commits: без секретов/токенов/паролей/`.env`-значений/реальных
email/абсолютных путей `/Users/...`/БД/бэкапов/media-бинарников; крупнейший
файл — frontend/app.js (~1.1 MB, текст). Readiness/settings не возвращают
секреты (тест). OAuth-токены только Fernet-encrypted в БД.

## Обязательные production env
`ENV=production`, `ADMIN_ALLOWLIST_EMAILS`, `TOKEN_ENCRYPTION_KEY`,
`COOKIE_SECURE=true`, `DATABASE_URL` (PostgreSQL), `REDIS_URL`,
`OPENAI_API_KEY` (⚠️ legacy-модуль требует его при импорте даже без
использования — известное ограничение), `FRONTEND_BASE_URL`, `API_BASE_URL`,
`CORS_ORIGIN`.
Optional: `PEXELS_API_KEY`, `GOOGLE_CLIENT_ID/SECRET` + `YOUTUBE_REDIRECT_URI`,
`AI_*` бюджеты, `VIDEO_*` настройки.

## План тестового deployment (НЕ выполнялся)
1. Backup prod: БД (`pg_dump`), `.env`, `output/` (BACKUP_RESTORE.md).
2. Проверить целевой commit: `28b135e`.
3. `scripts/predeploy_check.sh` локально.
4. Доставка кода через git (без `.env`, `data/`, `output/`, `cache/`, logs).
5. `pip install -r requirements.txt`.
6. Повторный PostgreSQL backup непосредственно перед рестартом.
7. Рестарт web (миграции additive, применяются на старте).
8. Frontend статика — из git (build-шага нет; integrity-гейт уже пройден).
9. Redis запущен (`redis-cli ping`).
10. Рестарт `python worker.py` (очереди generation+render).
11. `GET /api/health` → 200.
12. Логин админа (allowlist).
13. `GET /api/readiness` → ready/degraded (не not_ready).
14. Smoke: /dashboard/, /channels/, /projects/, /publications/,
    /factory-analytics/, /factory-settings/.
15. Тестовый рендер fixture-проекта → completed.
16. ffprobe MP4 + download.
17. Rollback-критерии: readiness not_ready; падение логина; рендер не
    выполняется при живом worker; 5xx на smoke-страницах.
18. Rollback: `git checkout <прежний commit>` + рестарт web/worker;
    БД из бэкапа только при порче данных.

## Known limitations
- Автозагрузка YouTube и Analytics sync не проверялись с реальным OAuth.
- Thread-fallback очереди (без Redis) теряет задачи при рестарте.
- Watch time/retention/revenue — только ручной ввод.
- Legacy SaaS-код (Stripe, Meta, старый dashboard) отключён от UI, но
  присутствует в кодовой базе; 11 legacy-тестов падают.
- `OPENAI_API_KEY` требуется при импорте app (legacy content pipeline) —
  переменная обязательна в production даже если TTS работает через бесплатный
  Edge; readiness показывает только configured/not configured, не значение.
  При корректной production-конфигурации (ключ задан) web и worker стартуют
  нормально — проверено validation-кейсом «valid → STARTED».

## Verdict
- **Test deployment: GO** — все factory-функции проверены локально E2E,
  gate зелёный, production validation fail closed подтверждён.
- **Public production use: NO-GO (пока)** — реальный OAuth, реальный YouTube
  upload и серверный деплой ещё не проверены; выполнить тестовый деплой,
  переподключить YouTube (новый scope), сделать один реальный upload на
  приватном видео и только затем открывать публикацию.
