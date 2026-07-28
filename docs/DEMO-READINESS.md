# AutoSocial.tech — Demo Readiness

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28
Legend: `[x]` verified · `[~]` partial (note) · `[ ]` not yet.

## Verdict: **PARTIAL** (core video flow is demo-recordable now)

The product presents and behaves as a real **AI Video Factory**: correct positioning at every entry point, a real & honest dashboard, a video-first create hub, a working short + long production pipeline that publishes to YouTube, real ops/health data, and captured screenshots. Not a full PASS because some in-app copy, the consolidated Ops-admin UI, and deep mobile/create-form/pipeline-UI verification remain.

## Product positioning
- [x] No misleading SaaS-first positioning at entry points (title, meta, OG, sidebar ×6 langs, create hub) — `[~]` some deep in-app copy remains.
- [x] Video Factory is the main product (nav, dashboard, create hub all video-first).
- [x] Social tools are secondary (moved under "Управление и дополнительные инструменты").
- [x] No fake testimonials (fabricated "SMB marketer" quote removed in all 6 languages).
- [x] No fake metrics (dashboard is real; landing "reach/engagement/audience growth" line replaced with the real production panel).

## Core flows
- [x] Dashboard — verified live vs seeded fixtures; all data real.
- [~] Create Short — video-first hub verified live; studio widget parity partial; production pipeline works (shorts publish in prod).
- [x] Create Long — pipeline verified end-to-end in production this session (long-form published).
- [~] Pipeline — status mapping documented (`PIPELINE-STATUS-MATRIX.md`); live-update/retry UI not fully re-verified.
- [~] History — code-reviewed; deep live audit pending.
- [ ] Video Details — not audited live (static-server deep-link limitation; needs SPA nav).
- [x] YouTube connection — status shown on dashboard + channel cards.
- [x] Publication status — real (Publications page + dashboard).

## Operations
- [x] Worker status · [x] Redis status · [x] FFmpeg status · [x] Queue visibility · [x] Failed jobs visibility · [x] Recent errors — all real via `infrastructure_status()` + `/factory-dashboard` (shown on dashboard "Инфраструктура" strip + alerts).
- [x] Database health — app + queries operate; surfaced implicitly.
- [~] Safe retry — render-job retry exists + is idempotent; a **consolidated Ops-admin UI** is designed but **not built** (blocker: `pageAdmin` source strings are mojibake-encoded — a safe inline edit is risky; see `ADMIN-DASHBOARD.md`).

## UX
- [x] Desktop checked (dashboard, create hub, projects, admin, system).
- [~] Mobile checked — screenshots captured at 375px; not every overflow exhaustively fixed.
- [x] Loading states · [x] Empty states (`нет данных`, `Каналов пока нет`) · [x] Error states (dashboard error card).
- [x] No critical console errors on audited pages.
- [~] No broken links / [~] No horizontal overflow — spot-checked; not exhaustively swept on mobile.

## Evidence
- [x] Screenshots saved → `docs/screenshots/` (8 files, desktop + mobile).
- [x] Test commands recorded (below) · [x] Test results recorded · [x] Known limitations documented (this file + audit docs).

## Tests
- Command: `USE_MOCK_PROVIDERS=true SYNC_JOBS=true python -m pytest tests/ -q` (mock providers → no paid AI calls, no real YouTube upload).
- Result: **251 passed, 14 failed** (3m06s). The 14 failures are **pre-existing** (verified: base commit == current for every failing assertion string) — from an earlier "first-post" onboarding refactor + a pipeline-stage rename whose tests weren't updated. **Zero failures were introduced by this task.**
- Added: `tests/test_factory_dashboard.py::test_dashboard_short_long_split` — passes (8/8 in that file).

## Screenshots
`docs/screenshots/`: `dashboard-desktop.png`, `dashboard-mobile.png`, `create-hub-desktop.png`, `create-hub-mobile.png`, `projects-desktop.png`, `operations-admin-desktop.png`, `operations-admin-mobile.png`, `system-health-desktop.png`. (No tokens, no real user email — dev seed `admin@autosocial.local` only — no server paths, no stack traces.)

## Can a demo video be recorded now?
**Yes, for the core Video Factory story:** positioning → dashboard (real metrics) → create hub (Short/Long) → projects/queue → publications/YouTube. **Avoid on camera** until fixed: the legacy `/admin` SaaS console and the deep create-video studio widgets (unverified parity).

## Remaining blockers (concrete)
1. Consolidated **Ops-admin** UI (data exists; `pageAdmin` mojibake makes a safe inline edit risky — needs an encoding-clean pass first).
2. **Video Details** live audit (needs SPA nav or a deep-link-capable dev server).
3. Deep **create-video studio** widget↔payload parity + post-create toast/job-id/background messaging.
4. **Mobile** overflow sweep across all pages.
5. Finish remaining in-app SMM copy reframing (non-blocking).
