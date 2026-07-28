# AutoSocial.tech — Demo Readiness Checklist

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28
Legend: `[x]` verified done · `[~]` partial (note) · `[ ]` not yet.

- [x] **Dashboard uses real data** — verified live against seeded fixtures; all metrics come from `/api/factory-dashboard` (real DB/queue/infra). No fake social metrics on the factory dashboard.
- [x] **Long video flow works** — end-to-end long-form render + YouTube publish confirmed in production this session (e.g. watch?v=IU_xKzM3b1k), incl. subtitles, cards, music.
- [~] **Short video flow works** — the short pipeline generates + publishes in production (verified this session, e.g. shorts/kN7IyA-P91E). Create-form field↔backend parity not yet fully audited.
- [~] **No incorrect SaaS positioning** — entry points fixed (17 shells, landing title/desc/OG, sidebar subtitle ×6 langs, create video-studio subtitle). Remaining in-app SMM copy + fabricated testimonial not yet reframed.
- [~] **Pipeline statuses are correct** — backend statuses are real and rich; the UI status→label mapping and live-update/retry behaviour not yet fully audited.
- [~] **Failed jobs are understandable** — dashboard surfaces failed counts + alerts that link to a fix location; per-job failure detail page not yet audited. Scheduler now self-heals stuck `running` jobs (commit `2fa6d86`).
- [~] **YouTube status is clear** — dashboard + channel cards show YouTube connection status (`✓` / not connected); full connect/OAuth flow not re-audited this iteration.
- [~] **Admin dashboard works** — legacy SaaS admin (users/plans/credits/revenue) works; the consolidated Video-Factory **Ops** admin is designed (data exists) but not yet built. See `ADMIN-DASHBOARD.md`.
- [~] **No exposed secrets** — `/factory-settings` is the settings surface; secret-masking to be explicitly verified.
- [~] **Demo screenshots ready** — desktop dashboard captured live during the audit; screenshots not yet saved as files under `docs/screenshots/`.
- [ ] **Login looks professional** — login page not audited beyond the public landing.
- [ ] **Retry works** — not verified.
- [ ] **Video preview works** — projects page offers Download; inline preview not verified.
- [ ] **Mobile layout works** — mobile viewports (375/768) not tested this iteration.
- [ ] **No critical console errors** — browser console not swept.
- [ ] **Demo video can be recorded** — pending the above.

## Confirmed strengths (real, honest)
- Real Video-Factory dashboard (metrics, alerts, activity, infra health) with honest empty states.
- Video-Factory-focused main navigation (SMM not dominant).
- Working short + long production pipeline publishing to YouTube.
- Ops/health data exists (worker/redis/queue/ffmpeg/disk) — no backend gap for it.

## Top blockers to "demo-ready"
1. Reframe remaining in-app SMM copy + remove fabricated testimonial/social-metric marketing.
2. Create Hub: lead with Video/YouTube; move Posts/Plans to a Social-legacy group.
3. Consolidate the Ops admin (data exists; presentation missing).
4. Verify create-form field parity, pipeline UI status mapping + retry, mobile layout, console errors.
5. Save desktop + mobile screenshots to `docs/screenshots/`.
