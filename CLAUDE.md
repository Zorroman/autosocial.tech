# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local Development
```bash
# Backend (port 5000)
python app.py

# Frontend (port 3000)
python -m http.server 3000 --directory frontend

# Worker (RQ job queue, required for async generation jobs)
python worker.py

# DB migrations (run once on setup or after schema changes)
python migrations.py

# Seed admin user
python seed_admin.py
```

- Front: `http://localhost:3000/login/`
- API: `http://localhost:5000/api/health`

### Tests
```bash
# Unit/integration tests (pytest)
python -m pytest tests/ -q

# Run a single test file
python -m pytest tests/test_saas.py -q

# Smoke tests
bash tests/smoke/run_smoke.sh

# Frontend unit tests (wizard_utils)
cd tests/smoke && node wizard_utils.test.js

# E2E tests (Playwright)
cd tests/e2e && npm install && npx playwright install
E2E_BASE_URL=https://dev.autosocial.tech npm run test:e2e

# Release verification (read-only HTTP checks against production)
python scripts/verify_release.py
```

### Docker
```bash
docker compose up -d --build
# Migrations run automatically on backend start via run_migrations() in app.py
```

### Logs
```bash
tail -n 200 logs/api.log
```

## Architecture

AutoSocial.tech is a SaaS platform for AI-powered social media content planning, generation, scheduling, and publishing (currently Facebook/Instagram via Meta Graph API).

### Stack
- **Backend**: Python/Flask, SQLAlchemy, PostgreSQL (prod) / SQLite (dev), Redis + RQ for async jobs
- **Frontend**: Vanilla JS SPA (`frontend/app.js`) + static HTML shells per page, no build step
- **AI**: OpenAI GPT-4o-mini for text, OpenAI TTS for video audio, Pexels/Pixabay for stock media
- **Billing**: Stripe subscriptions + credit system

### Key Files
| File | Role |
|---|---|
| `frontend/app.js` | Entire frontend runtime — dashboard, create, calendar, history, billing, admin. All UI state lives here. |
| `api.py` | All Flask routes (~350k chars). Entry point for every frontend-facing API call. |
| `app_services.py` | Core business logic shared across routes (generation, scheduling, history). |
| `app.py` | Flask app factory, background loops, migration bootstrap, niche catalog seeding. |
| `content_pipeline.py` | Text generation pipeline — all post/draft generation passes through here. |
| `plans_catalog.py` | Plan definitions and public plan model. Single source of truth for tier limits. |
| `services/entitlements.py` | Feature gating and usage enforcement — checks against plans_catalog. |
| `app_models.py` | SQLAlchemy ORM models (AppUser, Plan, Subscription, Campaign, etc.). |
| `auth.py` | Auth helpers (session tokens, email verification codes). |
| `stripe_service.py` | Stripe billing integration (subscriptions, webhooks, portal). |
| `facebook_api.py` | Meta Graph API integration for publishing. |
| `worker.py` + `cron_jobs.py` | RQ worker and scheduled jobs (autoposting, credit resets). |
| `migrations.py` | All DB schema migrations, applied in order at startup. |
| `niche_catalog.py` | Niche/template catalog definitions, seeded into DB at startup. |

### Frontend Pages
All pages share `frontend/app.js` and `frontend/styles.css`. Each page has a static HTML shell:
- `/` → `frontend/index.html` (landing)
- `/dashboard/` → `frontend/dashboard/index.html`
- `/create/` → `frontend/create/index.html`
- `/billing/` → `frontend/billing/index.html`
- `/connections/` → `frontend/connections/index.html`
- `/history/`, `/settings/`, `/admin/`

Niche-aware UI behavior depends on `frontend/data/nicheTemplates.js`.

### Generation Pipeline
```
frontend/app.js → POST /api/create/generate
  → api.py (route) → content_pipeline.py (text gen) / app_services.py
```
The AI Director flow (`/api/ai/director/*`) also passes through `content_pipeline.py`.

### Media Pipeline
- **Post images**: `backend/services/media/pexels_service.py` → `image_picker.py` → `media_query_builder.py`
- **Video footage (Content Factory — the live automated Shorts/long-form pipeline)**:
  `footage/providers/pexels.py` + `footage/providers/pixabay.py` (both queried
  and ranked together, see `media_diversity.py`) → `footage_library.py`
  (`score_candidates`/`acquire_segment_asset` — cooldown, category-repeat
  penalty, reservation). `footage_matcher.py` + `footage/ranking.py` are a
  separate, more elaborate matcher used only by the older single-video
  `video_pipeline.py` path below, not by the live channel automation.
- GPT image generation is permanently disabled — do not reintroduce it.

### Video Pipeline
`video_pipeline.py` (`/api/video/generate` — a standalone single-video
endpoint, separate from the Content Factory's channel automation above) →
`video_script_generator.py` → `video/tts.py` + `video/subtitles.py`
Artifacts stored under `BASE_DIR`: `cache/footage/`, `output/videos/`, `output/audio/`.

### Auth Flow
Email-based registration with verification code (no passwordless magic link, codes have TTL). Google OAuth and Facebook OAuth also supported. Session tokens stored in cookies. Auth behavior is in `auth.py` and auth routes in `api.py`.

### Plan / Entitlements Flow
`plans_catalog.py` defines all tier limits → `services/entitlements.py` enforces them at the API layer before any action. Never widen entitlements without an explicit task requirement.

## Critical Constraints

- **Shared high-risk files** (`frontend/app.js`, `api.py`, `app_services.py`, `app.py`, `content_pipeline.py`, `plans_catalog.py`): before editing any of these, state the blast radius and verify adjacent flows after the change.
- **Never reintroduce deprecated GPT image generation** into any production path.
- **Do not silently change** route shapes, response payloads, query params, or persisted field meanings.
- **Prefer 1–3 file edits**; if more files must change, justify why the smaller scope is insufficient.
- **No broad refactors** unless the task explicitly asks for one.
- `deploy/release/*` are legacy snapshots — do not treat as active runtime.

## Task Format

Use `TASK_TEMPLATE.md` when writing task specs. Required response format for any non-trivial change:
1. Solution summary
2. Files changed
3. Why this file scope was necessary
4. Verification performed
5. Untouched but potentially affected domains
6. Risks or assumptions
