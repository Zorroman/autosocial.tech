# AutoSocial.tech — Demo Readiness

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28
Legend: `[x]` verified · `[~]` partial (note) · `[ ]` not yet.

## Verdict: **PASS** for the Video Factory demo

All internal blockers named in the previous iteration are closed: the suite is green (267 passed / 0 failed), Operations Overview exists with real data, Video Details was opened in the browser in every state (and a real bug fixed), the responsive sweep is clean (0 overflow, 0 console errors across 10 pages × 4 viewports), and the screenshots are recaptured with a neutral demo user. The remaining items below are **non-blocking follow-ups**, not demo blockers.

## Product positioning
- [x] No misleading SaaS-first positioning — entry points (17 shells, landing title/desc/OG), sidebar subtitle (6 langs), landing hero (ru/en) and the create hub all describe the AI Video Factory.
- [x] Video Factory is the main product — nav, dashboard, create hub are video-first.
- [x] Social tools are secondary — posts/plans moved under "Управление и дополнительные инструменты"; backend untouched.
- [x] No fake testimonials — fabricated "SMB marketer" quote removed in all 6 languages.
- [x] No fake metrics — dashboard is 100% backend-derived; landing "reach/engagement/audience growth" replaced with the real production panel.

## Core flows (verified in a browser on the local dev stack)
- [x] **Dashboard** — real metrics incl. short/long split, alerts linking to fix locations, activity feed, infra strip.
- [x] **Create Hub** — Short and Long are the two primary actions.
- [x] **Create Short / Create Long** — both studio routes load (deep-linked via the new SPA fallback); duplicate-render protection covered by tests.
- [x] **Projects + render queue** — real list, statuses shown as human labels ("Рендерится", "Ошибка"), queue table.
- [x] **Video Details** — opened for completed / processing / failed / published: pipeline conveyor, retry ("↻ Повторить этап"), scenes, script, error text, "✅ Опубликовано на YouTube ↗" with the video link, MP4 download.
- [x] **Operations Overview** — real health, queues, failed jobs, recent errors and publications.
- [x] **YouTube connection / publication status** — visible on dashboard, channel cards, project details.

## Operations
- [x] Worker · [x] Redis · [x] Database · [x] Backend API · [x] FFmpeg · [x] Disk — all real, with a Healthy/Degraded/Offline/**Unknown** vocabulary; the worker correctly displayed **Offline** during verification (no fake green).
- [x] Queue visibility · [x] Failed jobs visibility · [x] Recent errors (each links to its fix location) · [x] Last-updated timestamp + manual refresh.
- [x] Safe retry — render retry exists and is state-checked; the publish path is idempotent (`youtube_video_id` guard); stale `running` jobs self-heal (commit `2fa6d86`).
- [x] No dangerous server-control actions added.

## UX
- [x] Desktop checked (1440×900, 1024×768) · [x] Mobile checked (375×812, 768×1024).
- [x] **No horizontal overflow** — automated `documentElement.scrollWidth <= innerWidth` on Login, Dashboard, Create Hub, Create Video, Projects, Operations, System, Settings, Publications, Channels × 4 viewports → **0 issues** (was 3, root cause `grid-template-columns: 260px 1fr` without `minmax(0,…)`).
- [x] **No console errors** — 0 across all 40 page-loads.
- [x] Loading (skeletons), empty (`нет данных`, honest empty lists) and error (retry card) states.
- [x] No broken media links — `output_url` is now emitted only when the rendered file exists.

## Evidence

### Tests
```
USE_MOCK_PROVIDERS=true SYNC_JOBS=true python -m pytest tests/ -q
267 passed, 0 failed, 0 skipped — 3m04s
```
Started at 14 failed; every one was diagnosed and fixed (see `git log`), including one real regression introduced by this branch (the Shorts daytime window made a scheduler test time-dependent) and one real code fix (`_channel_dict` tolerating a channel without `publishing_mode`).

### Playwright
- Responsive/console sweep: 10 pages × 4 viewports → 0 overflow, 0 console errors.
- Screenshot capture: 12 screenshots, authenticated as `demo@autosocial.local`.

### API smoke (all 200)
`/api/health`, `/api/me`, `/api/factory-dashboard`, `/api/readiness`, `/api/video-projects`, `/api/channels`.

### Screenshots (`docs/screenshots/`)
`dashboard-desktop.png`, `dashboard-mobile.png`, `create-hub-desktop.png`, `create-hub-mobile.png`, `create-short-desktop.png`, `create-long-desktop.png`, `projects-desktop.png`, `video-details-desktop.png`, `video-details-mobile.png`, `operations-desktop.png`, `operations-mobile.png`, `system-health-desktop.png`.
No admin seed email (uses `demo@autosocial.local`), no tokens, no stack traces, no server paths.

### Local dev stack
```bash
./scripts/dev-start.sh          # backend (mock providers, isolated SQLite) + SPA-fallback frontend
./scripts/dev-start.sh --stop
```
Deep links work: `/operations`, `/projects/1`, `/create/video`, `/video/2`, `/admin/`.

## Non-blocking follow-ups
1. Remaining in-app SMM copy in deeper legacy screens (posts studio, planner, calendar) — the primary Video Factory surfaces are done.
2. `/admin` is still the legacy SaaS console (users/plans/credits/revenue). Operations is now the ops surface; consolidating them further is optional.
3. `pageAdmin`'s source strings are mojibake-encoded — worked around (Operations lives in its own UTF-8 module); a dedicated encoding cleanup would still be healthy.
4. Post-submit UX polish in the create studio (explicit toast + job id + "continues in background" copy).

## Can a demo video be recorded now?
**Yes.** Recommended path: landing/positioning → Dashboard → Create Hub (Short/Long) → Projects + render queue → Video Details (completed **and** failed) → Operations → mobile view. Avoid the legacy `/admin` console on camera.
