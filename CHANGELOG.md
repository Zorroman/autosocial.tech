# Changelog

This project doesn't cut tagged releases — it's a continuously-deployed
single-operator system, not a versioned library. This log summarizes real,
notable changes from git history, grouped by period, newest first. It is not
every commit (there are 280+); it's the ones that changed what the system
actually does or how it's built. For the reasoning behind the biggest ones,
see [`CASE_STUDIES.md`](CASE_STUDIES.md) and [`docs/adr/`](docs/adr/).

## 2026-07/08 — Module rename, real Docker/E2E verification, production hardening

- Dropped the `saas_` prefix from the core backend modules
  (`saas_api.py` → `api.py`, `saas_services.py` → `app_services.py`, etc.) —
  the names predated the pivot to a video factory and collided with Python's
  standard-library-adjacent naming conventions.
- `docker-compose.yml` genuinely didn't work from a clean clone (wrong build
  context, missing port mappings, a Caddy reverse-proxy config where bare
  directives silently lost precedence to the static file server). Verified
  via repeated from-scratch clean-room runs: fresh clone, `--no-cache` build,
  full stack up, real Playwright suite against it — not a claim, an actual
  repeated procedure.
- Added `tests/e2e/factory.spec.ts` — a real Playwright suite (real login,
  real HTTP, no route mocking) against the Docker Compose stack, wired into
  CI alongside `ruff`/`pytest`/`gitleaks`/a compose-config-validation job.
- `ApiToken` never expired and had no revocation path. Added a TTL,
  server-side `POST /api/auth/logout`, and a backward-compatible migration
  (legacy sessions get a bounded grace period, not an immediate log-out).
  Verified against a simulated pre-migration database and, separately, on
  the real production database (441 existing tokens, all backfilled
  correctly, zero data loss in any other table).
- Media Diversity Engine: the live footage-selection path only ever called
  Pexels — Pixabay support existed in the codebase but was wired to an
  unused legacy pipeline. Both providers are now searched and ranked
  together, plus category-level repeat protection and a 90-day/500-use
  long-term cooldown, on top of the existing per-scene/per-channel cooldown
  system.
- A controlled production deployment applied the above (backend + worker
  only; Postgres/Redis/Caddy untouched) with a full backup/rollback plan,
  a real post-deploy render with real providers, and no interruption to the
  live automatic publishing schedule.

## 2026-07 — Portfolio hardening & security remediation

- Pre-publication `gitleaks` audit found real secrets in git history
  (OpenAI key, Stripe test credentials); targeted `git filter-repo` rewrite,
  independently re-verified from a fresh clone. Full incident in
  [`SECURITY.md`](SECURITY.md).
- Worker health check fixed: "offline" was a false positive caused by a
  120-second threshold roughly 3× stricter than the RQ library's own
  liveness window ([`CASE_STUDIES.md` #2](CASE_STUDIES.md#2-the-worker-was-never-offline)).
- Fixed a routing-precedence bug sending both Create Hub video buttons to
  the wrong (legacy) page ([`CASE_STUDIES.md` #7](CASE_STUDIES.md#7-a-button-that-looked-right-and-went-to-the-wrong-page)).
- Purged remaining pre-pivot "SMM/autoposting" copy from the live login page
  and the shared brand logo asset (both were missed by an earlier landing-page
  rewrite because they're separate rendered surfaces from the static shell).
- Dead code removed: an unused `Python/` directory, orphaned React
  components with no build tooling to run them, a debug token-printer
  script.
- Added CI (`pytest` + `gitleaks` on every push), `LICENSE`, and this
  documentation set (`ARCHITECTURE.md`, `SYSTEM_DESIGN.md`, `PRODUCTION.md`,
  `DEPLOYMENT.md`, `TESTING.md`, `OPERATIONS.md`, `SECURITY.md`,
  `CASE_STUDIES.md`, `ENGINEERING_DECISIONS.md`, `LESSONS_LEARNED.md`,
  `PERFORMANCE.md`, `docs/adr/`).
- Fixed a horizontal-overflow CSS bug found by an automated responsive
  sweep (10 pages × 4 viewports), a debug-info leak on the System page, and
  fabricated testimonial/metrics copy removed from the landing page.
- Added an Operations dashboard (real infra/queue state, not mock data) as
  a deliberately separate module to route around character-encoding
  corruption in the legacy admin block — see the relevant decision in
  [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

## 2026-07 — Long-form video factory

- Memory-safe chunked long-form renderer: peak RSS bounded at 383–623 MB
  independent of video length, replacing a monolithic FFmpeg filter graph
  that reliably OOM-killed the worker on longer videos
  ([`CASE_STUDIES.md` #1](CASE_STUDIES.md#1-memory-safe-long-form-rendering)).
  Ken Burns pans, footage/photo interleaving, natural TTS voice, section
  duration top-up to hit target length.
- Word-level forced-alignment subtitles via Whisper, replacing proportional-
  timing guesses ([`CASE_STUDIES.md` #3](CASE_STUDIES.md#3-subtitle-sync-via-forced-alignment)).
- Scheduler self-heal for stale `running` state so a crashed render can't
  silently block all future generation
  ([`CASE_STUDIES.md` #4](CASE_STUDIES.md#4-the-scheduler-that-stopped-without-saying-anything)).
- Auto-publish safety gates, per-pillar YouTube playlist sorting, semantic
  multi-stage footage matching (rejecting abstract/CGI "screensaver" clips
  in favor of literal footage matches).

## 2026-02 to 2026-07 — YouTube video pipeline foundation

- Google OAuth YouTube-connect flow and channel sync added alongside the
  existing Meta connection.
- Core video pipeline built from scratch: shot matching, TTS, subtitles,
  FFmpeg render, footage provider integration (Pexels/Pixabay) with
  cooldown-based de-duplication, queue-safe render workflow.
- Private YouTube Shorts project/render workflow and the first real
  YouTube publish.

## 2026-02 — Initial snapshot

- Initial commit: a general social-media SaaS tool (post generation,
  scheduling, and publishing to Facebook/Instagram via the Meta Graph API,
  with Stripe billing and multi-tenant plan tiers). That surface still
  exists today as a secondary, working feature — see the "Keeping legacy
  code paths" decision in [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md)
  for why it wasn't deleted when the product repositioned around video.
