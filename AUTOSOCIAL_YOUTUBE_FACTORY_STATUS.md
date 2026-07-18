# AutoSocial → Private YouTube Factory: Status

Дата: 2026-07-18. Сессия перестройки из публичного SaaS в закрытую личную систему
управления YouTube-каналами.

## Состояние до изменений

- Публичный SaaS: регистрация по email-коду, Google/Facebook OAuth-логин, тарифы,
  Stripe, trial, кредиты.
- Рабочий FFmpeg-видеопайплайн (`video_pipeline.py` → TTS → footage → субтитры →
  рендер), очередь RQ/Redis с thread-fallback, YouTube OAuth и upload-функция.
- `frontend/app.js` — монолит ~18k строк; ранее повреждался mojibake
  (см. `frontend/app.js.bak_mojibake` — резервная копия повреждённой версии).

## Root cause frontend corruption

Точный исторический источник не воспроизводим постфактум; резервная копия
`app.js.bak_mojibake` показывает классическое повреждение UTF-8 → `????` при
передаче/записи файла в не-UTF-8 локали (shell-подстановки / некорректный
transfer). Защита добавлена: `scripts/check_frontend_integrity.sh` — проверка
JS-синтаксиса, валидности UTF-8, счётчик `????` (>3 → fail), SHA-256 checksum.
Запускать перед каждым деплоем; при fail деплой останавливать.

## Что сделано в этой сессии

### Private admin mode (fail closed)
- `saas_settings.py`: `PRIVATE_ADMIN_MODE` (default **true**), `ADMIN_ALLOWLIST_EMAILS`.
- `saas_auth.py`: `is_email_allowed()` — единый guard; встроен в `require_auth`,
  т.е. действует на **все** защищённые endpoints (генерация, видео, очередь,
  файлы, публикации, admin, billing). Пустой allowlist в private mode = доступ
  запрещён всем (fail closed).
- `saas_api.py`: `/auth/register` → всегда 403 в private mode; login (пароль,
  challenge-код, Google/Facebook OAuth) — только для allowlist; старые сессии
  вне allowlist получают 403 при каждом запросе.
- `app.py`: при `PRIVATE_ADMIN_MODE=true` и пустом allowlist — critical-лог;
  в `ENV=production` — остановка запуска с ошибкой.
- Frontend: `authMode` по умолчанию `login`; кнопка переключения на регистрацию
  удалена; hero-CTA «Начать бесплатно» → «Войти»; pricing-секция, trial-пиллы и
  финальный register-CTA удалены; ссылка Billing убрана из навигации.

### Channels (Stage C)
- Модели `Channel` (все требуемые поля: niche, language, voice, visual style,
  allowed/prohibited topics, duration, format, timezone, status
  testing/active/paused/archived, YouTube refs, JSON-настройки) и `ChannelIdea`
  в `saas_models.py`; таблицы создаются автоматически (additive, create_all).
- `channels_api.py` — новый blueprint `/api/channels*`:
  list/create/get/patch/delete (delete блокируется при зависимостях → 409,
  вместо этого архивирование), лимит 10 каналов, изоляция по owner_user_id,
  идеи: create/list/patch-status, генерация идей через OpenAI с контекстом
  канала и правилами качества эзотерического контента (без медицинских/
  финансовых/юридических утверждений и «гарантированных предсказаний»).
- Frontend: страница **/channels/** (список, статусы, создание, настройки,
  идеи, AI-генерация идей) + пункт «Каналы» в навигации.
- `seed_channel.py` — CLI-создание первого эзотерического канала (создан:
  id=1, slug `esoterica`, все параметры редактируемы).

### Безопасность
- `/api/media/<path>`: добавлен запрет dotfiles и ограничение выдачи только
  каталогами `output/`, `cache/`, legacy media (раньше при дефолтном BASE_DIR
  мог отдать любой файл проекта, включая `.env`).
- FFmpeg вызывается через argument arrays (проверено, без shell-конкатенации).

### Тесты
- `tests/test_private_admin.py` — 10 тестов: register 403 (всегда), login
  allowlist, login вне allowlist 403, старая сессия вне allowlist 403, аноним
  401, пустой allowlist fail closed, CRUD каналов, изоляция, лимит 10, идеи.
- `tests/test_render_fixture.py` — настоящий рендер MP4 через production
  `render_video()` на локальных fixtures + ffprobe-валидация (h264, 1080×1920,
  yuv420p, aac, длительность).
- `tests/conftest.py` — legacy SaaS-тесты выполняются в public-режиме.

## Реальный видеорендер (проверено)

- Файл: `output/videos/test_esoteric_short.mp4` (копия в
  `data/output/videos/` для выдачи через API).
- ffprobe: h264 1080×1920 yuv420p, aac 44100 Hz, 9.0 s, ~136 KB, русские
  субтитры вожжены в кадр.
- Download: `GET /api/media/output/videos/test_esoteric_short.mp4` → 200.
- ⚠️ TTS и генерация сценария через OpenAI **не тестировались с реальным
  провайдером**: аккаунт OpenAI возвращает 429 `insufficient_quota`. Рендер
  проверен на локальных fixtures (синтетические клипы + тон вместо голоса).

## Статус функций

Полностью работает: private-admin auth, Channels CRUD + идеи (ручные),
FFmpeg-рендер Shorts, download MP4, очередь (RQ при Redis, thread-fallback),
интеграционная защита всех API.

Частично: генерация идей/сценариев/TTS — код рабочий, но требует пополнения
квоты OpenAI; Pexels footage — ключ есть, не прогонялся в этой сессии;
YouTube OAuth/upload — код существует (`_finalize_youtube_oauth_connect`,
`_publish_youtube_video_from_url`), не тестировался.

Отключено: публичная регистрация, pricing/trial UI, ссылка Billing.
Legacy (код остался, UI убран): Stripe, тарифы, entitlements, Meta-постинг.
Не реализовано: посценный редактор проектов, страница Render Queue UI,
аналитика каналов, AI cost tracking per-channel, автопубликация.

## Ограничения очереди (честно)

Без Redis очередь работает через in-process поток: задачи теряются при
рестарте процесса. Для надёжности запускать Redis + `python worker.py`.

## Как пользоваться

1. `.env`: `PRIVATE_ADMIN_MODE=true`, `ADMIN_ALLOWLIST_EMAILS=<ваш email>`.
2. Админ: `ADMIN_EMAIL=... ADMIN_PASSWORD=... python seed_admin.py` (CLI, без
   HTTP; пароль не логируется).
3. Первый канал: `python seed_channel.py`.
4. Запуск: `python app.py` (5000) + `python -m http.server 3000 --directory
   frontend` + при Redis `python worker.py`.
5. Вход: `/login/` → email-код (или `ALLOW_ADMIN_DIRECT_LOGIN=true` для
   прямого входа по паролю).
6. Каналы: `/channels/` — создание/настройки/идеи.
7. MP4: `BASE_DIR/output/videos/`; скачивание `GET /api/media/output/videos/<file>`.
8. YouTube: подключение через `/connections/` (нужны GOOGLE_CLIENT_ID/SECRET и
   включённый YouTube Data API v3).

## Env variables (см. .env.example)

Ключевые новые: `PRIVATE_ADMIN_MODE`, `ADMIN_ALLOWLIST_EMAILS`.
Требуемые для генерации: `OPENAI_API_KEY` (нужна активная квота!),
`PEXELS_API_KEY`, опц. `PIXABAY_API_KEY`. Для YouTube: `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `YOUTUBE_REDIRECT_URI`.

## VideoProject / сцены / Render Queue (добавлено 2026-07-18, вторая итерация)

- Модели: `VideoProject` (channel_id, idea_id, script, voice_mode tts/file/silent,
  aspect_ratio, output_path, error, статусы draft/ready/rendering/rendered/
  failed/archived), `VideoScene` (order, voiceover_text, on_screen_text,
  durations, visual_type, selected_media_path, transition), `RenderJob`
  (pending/processing/completed/failed/cancelled, progress, attempts/max,
  error, worker, timestamps, output). Additive, create_all; dev-БД забэкаплена
  (`autosocial.db.bak_*`).
- API (`video_projects_api.py`, всё за require_auth + owner-изоляция):
  `/video-projects` CRUD, `/split-scenes` (разбивка сценария на сцены по
  предложениям, ~2.5 слова/сек; отказ перезаписи без `replace=true`),
  scenes CRUD (валидация media-путей: только разрешённые каталоги — path
  traversal заблокирован, `/etc/passwd` → 400), `/scenes/<id>/fixture-media`
  (честная локальная фикстура, visual_type='fixture'),
  `/video-projects/<id>/render` (защита от дубликатов → 409),
  `/render-jobs` list/get/retry/cancel.
- Очередь: RQ-очередь `render` (worker.py теперь слушает generation+render);
  без Redis — thread-fallback; `SYNC_JOBS=true` — синхронно (тесты).
  Прогресс пишется на реальных стадиях (5/15/30/40/100), без симуляции.
- Voiceover: `tts` (edge-tts/OpenAI через video/tts.py), `file`, `silent`
  (честная тишина для технических тестов).
- Frontend `/projects/`: выбор канала, список проектов, сценарий, разбивка на
  сцены, редактирование сцен, привязка фикстур, рендер, очередь с прогрессом/
  попытками/ошибками/retry/cancel, preview `<video>` и скачивание MP4.
- E2E проверено через UI: проект «Символ чёрной луны» (эзотерический канал) →
  сцены → фикстуры → RQ-рендер → `data/output/videos/project_1_job_1.mp4`
  (ffprobe: h264 1080×1920 yuv420p 30fps, aac 44100, 12.4 s) → preview в
  браузере (video readyState=4) → download 200 (70500 bytes).
- Тесты: `tests/test_video_projects.py` — 5 тестов, включая полный E2E-рендер
  реального MP4 с ffprobe-валидацией и download через API.

## Реальный TTS и стоковые медиа (2026-07-18, третья итерация)

### TTS (протестировано с реальным провайдером)
- Провайдер: **Edge TTS (edge-tts 7.2.8)** — бесплатный, работает без ключей.
  Протестированный голос: **ru-RU-DmitryNeural**. OpenAI-голоса доступны в
  списке, но требуют активной квоты (preflight честно вернёт ошибку).
- Endpoints: `GET /api/tts/voices` (доступность провайдеров),
  `POST /api/tts/preview` (тест голоса, только по явному действию),
  `POST /api/video-projects/<id>/tts` — озвучка всех сцен: preflight провайдера
  (без тихого fallback), генерация, ffprobe-проверка, обновление реальных
  длительностей сцен, `voice_mode='file'`.
- Реальный результат: `data/output/audio/project_2_voiceover.mp3`, 18.36 s,
  длительности сцен 7.92 / 7.99 / 2.45 s.

### Стоковые медиа (Pexels, реальный ключ)
- `POST /api/scenes/<id>/stock-search` — реальный поиск, приоритет portrait
  9:16, fallback landscape (в UI помечается «→ crop 9:16»).
- `POST /api/scenes/<id>/stock-select` — SSRF-safe: клиент передаёт только
  `video_id` + query; сервер сам повторяет поиск и скачивает по URL от Pexels
  API (пользовательские URL не принимаются).
- `POST /api/video-projects/<id>/auto-media` — подбор для всех сцен: query из
  `stock_search_query`/`visual_prompt`/ключевых слов; не повторяет один клип
  подряд; не перезаписывает уже выбранное медиа без `overwrite`.
- Метаданные (source, author, license, w×h, duration, orientation) хранятся в
  `video_scenes.media_meta_json` (additive-миграция) и показываются в UI.
- Использовано в E2E: 3 реальных вертикальных клипа Pexels
  (19997487 © Rachit Gupta; 18202294 © Enes Salih Gökçek;
  27546122 © Ünal Karabiber; лицензия Pexels License, free to use).

### Новый реальный E2E (без фикстур)
Проект «Свечи и лунный свет» (эзотерический канал): сценарий → 3 сцены →
edge-TTS → 3 реальных Pexels-клипа → SRT-субтитры → RQ-очередь →
`data/output/videos/project_2_job_3.mp4` → preview в UI → download 200.
ffprobe: **h264 1080×1920 yuv420p 30 fps, aac 24000 Hz, 18.34 s, 5 933 502 bytes**.
- Fallback silent/fixture сохранён и по-прежнему покрыт тестами
  (test_video_projects.py::test_full_e2e_render_real_mp4 — 16 passed).
- Fix: `worker.py` теперь загружает `.env` (иначе RQ-worker писал вывод в
  другой BASE_DIR); RQ-worker слушает очереди generation+render.

## YouTube publication workflow (2026-07-18, четвёртая итерация)

### Аудит существовавшей интеграции — статус: partial
Реально работало: OAuth start/callback/connect/disconnect/status,
Fernet-шифрование токена (TOKEN_ENCRYPTION_KEY), чтение snippet канала,
resumable-upload-функция в коде. Пробелы: scope только `youtube.readonly`
(upload невозможен), refresh_token не сохранялся, выбор из нескольких
YouTube-каналов отсутствовал, связи с внутренним Channel не было.

### Исправлено / добавлено
- Scope OAuth: + `youtube.upload`; refresh_token теперь сохраняется
  (зашифрованным) — **существующие подключения нужно переподключить**, чтобы
  получить новый scope и refresh_token.
- Channel ↔ YouTube: поля `youtube_channel_title`, `youtube_connection_status`,
  `youtube_connected_at`, `youtube_social_account_id`, `youtube_last_verified_at`
  (additive-миграция). Endpoints: `/channels/<id>/youtube/status|available|
  link|verify|unlink` — реальный список каналов аккаунта (maxResults 50),
  выбор канала, защита от привязки одного YT-канала к двум внутренним.
- Модель `Publication` (все требуемые поля; статусы draft/ready/uploading/
  published/failed/cancelled; режимы manual/immediate/scheduled).
- API `publications_api.py`: prepare-publication (валидации: render completed,
  MP4 существует, дубликаты → 409), CRUD, manual-complete (парсинг URL/ID,
  проверка формата, дубликат video_id → 409), upload (очередь; guards:
  YouTube подключён, файл есть, не published/uploading, scheduled_at в будущем),
  retry только для failed без сохранённого video_id.
- Upload job: resumable upload YouTube Data API v3, token refresh через
  refresh_token, честная обработка quota (`quota_exceeded`), published только
  после подтверждения API (video id).
- UI: раздел «Публикации» (таблица со статусами/режимом/ссылкой/ошибкой/retry),
  редактор публикации в проекте (title/description/tags/privacy/режим/дата,
  «Скачать MP4», manual-complete, «Автозагрузка» с confirm), YouTube-блок в
  настройках канала (статус, подключить/выбрать канал/проверить/переподключить/
  отключить; при отсутствии OAuth показываются имена недостающих переменных).
- Токены не попадают в ответы API, UI и логи (проверено grep-сканом).

### Manual-first flow — проверен в UI end-to-end
Проект «Свечи и лунный свет» → «Подготовить публикацию» → редактор → «Скачать
MP4» → ввод YouTube URL → «Отметить как опубликованное» → статус
«Опубликована» в разделе Публикации.

### Реальный upload НЕ выполнялся
По правилу этапа: реальная загрузка на канал требует отдельной явной команды.
Автозагрузка покрыта mocked-тестами (success, quota error, token failure).
Для реальной загрузки нужно: переподключить YouTube (новый scope), привязать
канал в «Каналы → YouTube», затем «Автозагрузка» в публикации.

Тесты: tests/test_publications.py — 8 тестов; всего 24 passed.

## Аналитика каналов и AI cost tracking (2026-07-18, пятая итерация)

### Аудит
Собственной YouTube-аналитики не было (legacy dashboard-метрики — Meta-посты,
не относятся к фабрике). Расходных моделей не было (только счётчики токенов в
openai_client). YouTube Analytics API не подключён.

### Модели (additive, create_all; dev-БД забэкаплена)
- `VideoAnalyticsSnapshot`: nullable-метрики (views/likes/comments/shares/
  subscribers/watch time/avg duration/avg %/impressions/CTR/revenue/currency),
  `data_source` manual|youtube_api, unique(publication, captured_at, source).
  Отсутствующая метрика = NULL, не ноль.
- `AICostRecord`: provider/model/operation_type/units/estimated+actual cost/
  currency/status/request_id (idempotency).

### API (`analytics_api.py`, всё за require_auth + owner-изоляция)
- Manual: POST `/publications/<id>/analytics`, GET `/analytics/snapshots`,
  PATCH/DELETE `/analytics/snapshots/<id>` (только manual-записи; API-snapshot
  редактировать/удалять нельзя). Валидация: неотрицательные, конечные,
  диапазоны, currency ISO-3, avg% ≤ 100.
- Sync: POST `/channels/<id>/analytics/sync` — YouTube Data API
  (scope `youtube.readonly` уже выдан, **новых scopes не требуется**):
  views/likes/comments по опубликованным видео канала; honest-ошибки
  quota→429, revoked token→409; manual-записи не трогаются; snapshots
  историчны (не перезаписываются). Watch time/revenue через Data API
  недоступны — вводятся вручную (YouTube Analytics API не подключался).
- Сравнение: GET `/analytics/channels?period=7|30|90|all` — по последнему
  snapshot каждого видео: total/avg/median/max/min views, engagement (guard
  деления на ноль), подписчики, watch time, revenue, AI cost,
  нормализованные: views/video, subs/video, cost/video, cost/1k views,
  views per dollar, revenue/video, net result; best/worst ролик.
- Расходы: GET `/analytics/costs` — бюджеты, потрачено день/месяц, остатки,
  failed-операции, последние записи.

### AI cost (`ai_pricing.py`)
- Центральная таблица цен (provider/model/unit/prices/currency/effective_date/
  source_note); override через env `AI_PRICING_JSON` без правки кода.
- Неизвестная модель → cost **NULL** («нет данных»), не ноль. Известно
  бесплатные: edge-tts, Pexels, локальный ffmpeg-рендер → честный 0.
- `record_cost` после реального выполнения (success/failed), идемпотентность
  по (operation_type, request_id) — retry не создаёт второй записи.
- Подключено: генерация идей (реальные токены из OpenAI-ответа), TTS
  (edge=0 / openai по символам), stock download, render (0, local),
  YouTube upload, analytics sync.
- Бюджеты (env): AI_DAILY_BUDGET, AI_MONTHLY_BUDGET, AI_MAX_COST_PER_VIDEO,
  AI_MAX_REGENERATIONS_PER_PROJECT, AI_MAX_VIDEOS_PER_DAY,
  AI_CONFIRM_COST_THRESHOLD. `check_budget` блокирует платную операцию до
  запуска (429 с понятным сообщением); бесплатные проходят всегда.

### UI `/factory-analytics/`
Сравнение каналов (периоды 7/30/90/всё, sync-кнопка на канал), ручной ввод
статистики (помечается manual), блок расходов (сегодня/месяц/остатки,
последние операции, «оценка» vs «факт», «нет данных» при неизвестной цене).
Пустые состояния вместо demo-цифр. Проверено в браузере: manual-замер 450
views сохранён, engagement 8.44% рассчитан.

### Реальный sync не выполнялся
Требует подключённого YouTube-канала (реальный OAuth — по отдельной команде).
Sync покрыт mocked-тестами: success, quota 429, revoked 409.

Тесты: tests/test_analytics_costs.py — 11; всего критических 35 passed.
Ограничение: старый Dashboard не переделан (legacy SaaS-метрики) — фабричная
аналитика живёт на «Аналитика каналов»; retention/watch time доступны только
manual, пока не подключён YouTube Analytics API (scope yt-analytics.readonly).

## Рекомендации следующего этапа

1. Пополнить квоту OpenAI → end-to-end тест идея→сценарий→TTS→рендер.
2. VideoProject-модель со сценами, привязанная к channel_id (сейчас видео-jobs
   живут в legacy campaign-модели без канала).
3. UI Render Queue поверх существующих `/api/video/jobs`.
4. AI cost tracking (модель уже считает токены в `openai_client`).
5. Postgres/Redis в production + прогон `scripts/check_frontend_integrity.sh`
   в deploy-скрипте.
