# AutoSocial — AI Video Factory

Autonomous production pipeline that writes, voices, edits, and publishes short- and
long-form video to YouTube — end to end, with no manual intervention in the default
path. It currently runs a real YouTube channel that publishes ~20 Shorts/day and one
long-form video/day, fully automated.

**This is not a SaaS demo or a wrapper around an API.** It is a working content
factory: script generation → TTS voiceover → stock-footage selection → FFmpeg
rendering (memory-safe on a 3.8 GB VPS) → subtitle burn-in (word-level, forced
alignment) → AI-generated metadata → YouTube upload, orchestrated by a scheduler
and background workers, with a real operations dashboard reading real
infrastructure state.

> Screenshots below are from a local dev environment with a neutral demo user and
> synthetic fixtures — not production data. See [`docs/screenshots/`](docs/screenshots/).

## Table of contents

- [What this actually does](#what-this-actually-does)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Engineering highlights](#engineering-highlights-worth-asking-about)
- [Known limitations](#known-limitations--honest-trade-offs)
- [License](#license)

## What this actually does

| Stage | What happens | Where |
|---|---|---|
| Ideation | An AI "Content Director" picks a topic per channel/pillar, avoiding recent repeats | `content_director.py` |
| Script | GPT-4o-mini writes narration; long-form gets a persona voice + a closing authorial synthesis | `video_script_generator.py` |
| Voice | OpenAI TTS (with a fallback chain), tone-controlled via `instructions` | `video/tts.py` |
| Visuals | Licensed stock photo/video selection (Pexels/Pixabay), multi-stage semantic matching, cooldown/reservation so footage doesn't repeat across a channel | `footage/`, `media_matcher.py`, `footage_matcher.py` |
| Render | Memory-safe chunked FFmpeg rendering — one segment at a time, never a monolithic filter graph (see [Engineering highlights](#engineering-highlights-worth-asking-about)) | `longform_render.py`, `video/render/render_video.py` |
| Subtitles | Word-level captions timed from the actual voiceover audio (Whisper forced alignment), not proportional guesses | `longform_pipeline.py` |
| Metadata | AI-generated titles/descriptions/tags, thumbnail | `ai_publisher.py` |
| Publish | Resumable YouTube upload, idempotent (no double-publish), auto-sorted into channel playlists | `publications_api.py` |
| Scheduling | Self-healing scheduler: daily quotas, publish-time windows, per-channel daily-limit reservation with row-level locking | `scheduler.py`, `longform_scheduler.py` |
| Ops | Real infrastructure health (backend/DB/Redis/worker/FFmpeg/disk/queues), never a faked green status | `factory_dashboard_api.py`, `frontend/operations.js` |

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Frontend    │◄────►│   Flask API   │◄────►│   PostgreSQL     │
│  (vanilla JS │      │  (saas_api.py │      │  (channels,      │
│   SPA)       │      │  + blueprints)│      │   projects, jobs)│
└─────────────┘      └───────┬──────┘      └─────────────────┘
                              │
                              ▼
                      ┌───────────────┐      ┌──────────────┐
                      │  Redis + RQ    │◄────►│  Worker       │
                      │  (job queue)   │      │  (scheduler + │
                      └───────────────┘      │  render jobs) │
                                              └───────┬──────┘
                                                       │
                              ┌────────────────────────┼────────────────────────┐
                              ▼                        ▼                        ▼
                      ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
                      │  OpenAI        │        │  FFmpeg        │        │  YouTube Data  │
                      │  (script, TTS, │        │  (render,      │        │  API v3        │
                      │  Whisper)      │        │  subtitles)    │        │  (upload)      │
                      └───────────────┘        └───────────────┘        └───────────────┘
```

Five Docker Compose services: `backend` (Flask API), `worker` (RQ + schedulers),
`postgres`, `redis`, `caddy` (reverse proxy/TLS). Full detail, including the
render-memory design and the reasoning behind key decisions, in
[`ARCHITECTURE.md`](ARCHITECTURE.md), [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md), and
[`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

## Quick start

```bash
cp .env.example .env               # fill in API keys (see Configuration)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python migrations.py               # schema (also runs automatically on app start)
python seed_admin.py               # creates a local admin user

python app.py                      # backend — http://localhost:5000
python -m http.server 3000 --directory frontend   # frontend — http://localhost:3000/login/
python worker.py                   # RQ worker + schedulers (needs Redis)
```

Or the full stack in containers:

```bash
docker compose up -d --build
```

For a self-contained local dev loop (mock AI providers, isolated SQLite DB, no
Redis/worker needed, and a small SPA-fallback server so deep links like
`/projects/12` work without a reverse proxy):

```bash
./scripts/dev-start.sh
./scripts/dev-start.sh --stop
```

## Configuration

All configuration is environment-driven — see [`.env.example`](.env.example) for the
full list. The essentials to run anything locally:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres in production, SQLite for local/dev |
| `OPENAI_API_KEY` | Script generation, TTS, Whisper alignment |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | Licensed stock footage |
| `GOOGLE_CLIENT_ID/SECRET` | YouTube OAuth + upload |
| `REDIS_URL` | Job queue (worker requires this) |
| `USE_MOCK_PROVIDERS=true` | Skip all paid AI calls — for tests/dev |

Set `USE_MOCK_PROVIDERS=true` and `SYNC_JOBS=true` for local development so you
never make a real (billed) API call by accident.

## Testing

```bash
USE_MOCK_PROVIDERS=true SYNC_JOBS=true python -m pytest tests/ -q
```

269 tests, all AI/YouTube calls mocked — the suite never spends money or touches a
real YouTube channel. Runs in CI on every push/PR (see
[`.github/workflows/tests.yml`](.github/workflows/tests.yml)), alongside a gitleaks
secret-scan. Playwright E2E and a scripted responsive/console sweep are documented
in [`TESTING.md`](TESTING.md).

## Deployment

Runs on a single small VPS (Hetzner CPX22, 3.8 GB RAM) via Docker Compose. Backend
and worker are independently tagged images, so a backend-only fix (no DB migration)
rebuilds and restarts in seconds without touching the worker mid-render. Full
procedure, backup/rollback strategy, and a walkthrough of a real production
deploy in [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`PRODUCTION.md`](PRODUCTION.md).

## Documentation

| Doc | What's in it |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Component breakdown, data flow, module map |
| [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) | Design constraints (3.8 GB RAM, single VPS) and how they shaped the system |
| [`PRODUCTION.md`](PRODUCTION.md) | What's actually running, real numbers, infra topology |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | How a deploy is actually done, safely, on this stack |
| [`OPERATIONS.md`](OPERATIONS.md) | Health checks, the Operations dashboard, runbooks |
| [`TESTING.md`](TESTING.md) | Test strategy, CI, E2E, the responsive-sweep tooling |
| [`SECURITY.md`](SECURITY.md) | Threat model, what was checked, and a real incident found + fixed |
| [`CASE_STUDIES.md`](CASE_STUDIES.md) | Deep dives on real bugs: root cause → decision → trade-off → result |
| [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md) | Why things are built the way they are, including calls I'd defend differently in hindsight |
| [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) | What this project actually taught me |

## Engineering highlights (worth asking about)

- **Memory-safe video rendering on a 3.8 GB box.** A naive render (one giant FFmpeg
  filter graph over all clips) OOM-kills at ~40% on this hardware. The renderer
  processes one still/clip at a time into a short segment, then stream-copies
  segments into chunks and chunks into the final file — peak RSS ~400–600 MB,
  independent of the video's total length. See
  [`CASE_STUDIES.md`](CASE_STUDIES.md#1-memory-safe-long-form-rendering).
- **A monitoring bug that was wrong by design, not by accident.** The worker
  health check flagged a perfectly healthy, idle worker as "Offline" because its
  120-second heartbeat threshold was three times stricter than the underlying
  queue library's own liveness window. Root-caused by reading the library's
  source, fixed, and verified live in production with a deliberate 130-second
  wait past the old broken threshold. See
  [`CASE_STUDIES.md`](CASE_STUDIES.md#2-the-worker-was-never-offline).
- **A live secrets-in-git-history incident, found and fixed before publishing.**
  A pre-publication `gitleaks` scan surfaced a real OpenAI key and Stripe test
  credentials committed months earlier. Full incident response: credential
  rotation, `git filter-repo` history rewrite across all branches and tags,
  independent re-verification via a fresh clone, before this repository was ever
  made public. See [`SECURITY.md`](SECURITY.md).

## Known limitations & honest trade-offs

This section exists on purpose — a reviewer will find these anyway, and I'd
rather state them than have them look like they were missed.

- **`frontend/app.js` is a single ~19k-line file** with no build step or module
  boundaries. It works, and 800+ consistent call sites of an `esc()` XSS-escaping
  helper show real discipline within that file — but it's a maintainability
  ceiling I'd address first on a team codebase. One legacy admin-panel block
  inside it has character-encoding corruption from an early migration; rather
  than risk further corrupting it with a blind edit, I built the newer
  Operations dashboard as a separate, cleanly-encoded module instead. See
  [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).
- **Deployment is manual (SSH + `docker compose build`), not GitOps.** Reasonable
  for a single-operator VPS at this scale; the first thing I'd change moving to a
  team environment.
- **The product's positioning evolved** from an earlier social-media-posting tool
  into today's YouTube video factory; some legacy code paths for that earlier
  scope still exist behind a secondary UI section rather than being deleted
  outright, to avoid breaking functionality that's still in occasional use.

## License

Proprietary — portfolio/evaluation use only. See [`LICENSE`](LICENSE).
