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

## Рекомендации следующего этапа

1. Пополнить квоту OpenAI → end-to-end тест идея→сценарий→TTS→рендер.
2. VideoProject-модель со сценами, привязанная к channel_id (сейчас видео-jobs
   живут в legacy campaign-модели без канала).
3. UI Render Queue поверх существующих `/api/video/jobs`.
4. AI cost tracking (модель уже считает токены в `openai_client`).
5. Postgres/Redis в production + прогон `scripts/check_frontend_integrity.sh`
   в deploy-скрипте.
