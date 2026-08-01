# AutoSocial.tech — Admin / Ops Dashboard (Iteration 4)

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28

## Current state

There are **two admin-ish surfaces**:

1. **`/admin`** — legacy **SaaS console**: users, plans (Free Trial/Starter/Growth/Agency), credits, a **Revenue panel** (Stripe/OpenAI/margin), "Сгенерировать статью", "Запустить контент-план". Real backend, but off-message for a Video Factory demo.
2. **`/factory-settings` ("Система") + the dashboard "Инфраструктура" strip** — the real **ops** surface.

## Ops data — which endpoints already exist (verified real)

| Ops need | Source | Status |
|---|---|---|
| Worker online/offline | `infrastructure_status()` → dashboard + `/api/readiness` | ✅ real |
| Redis health | `infrastructure_status()` | ✅ real |
| Render queue length | `infrastructure_status()` (`render_queue_size`) | ✅ real |
| FFmpeg available | `infrastructure_status()` | ✅ real |
| Disk free | `infrastructure_status()` | ✅ real |
| Failed jobs | `/api/factory-dashboard` `overview.jobs_failed` + alerts | ✅ real |
| Failed publications | `/api/factory-dashboard` `publications.failed` + alerts | ✅ real |
| Active/pending jobs | `overview.jobs_pending/processing` | ✅ real |
| Recent publications | dashboard activity feed | ✅ real |
| Recent errors | dashboard alerts (each links to a fix location) | ✅ real |
| API integration status | `/factory-settings` (OpenAI/Pexels/Pixabay/YouTube) | ✅ real |

**Conclusion:** the ops/admin data the task lists is **not a backend gap** — it exists and is honest. What's missing is a single consolidated **Ops dashboard** presentation.

## Backend gaps (would need new read-only endpoints)
- **Memory usage** — not currently exposed (disk is). Low priority; add a read-only field to `infrastructure_status()` if wanted.
- **Scheduled jobs list** (next long-form / next shorts due-times) — derivable from `Channel.last_generated_at` / `longform_last_generated_at`; not surfaced as a list.
- **Dead-letter / stuck-job view** — the scheduler now self-heals stale `running` jobs (see commit `2fa6d86`); a read-only "stuck jobs" panel could surface them before auto-reset.

## Recommendation (not yet implemented — Iteration 4 remaining)
- Promote **Система (ops)** to the primary Admin surface: Overview (worker/redis/queue/ffmpeg/disk), Active jobs, Failed jobs (with **retry**, gated to allowed statuses + confirmation), Render queue, Publishing queue, Recent errors, Integrations.
- Keep the SaaS user/plan/credit console behind a **"Billing / Users (legacy)"** tab.
- **Dangerous actions** (cancel/retry/clear queue/republish/delete) must have a confirmation dialog **and** a backend state-check. The publish path already enforces idempotency (no double-upload) and the scheduler self-heals stuck jobs.

## Implemented (2026-07-28)
**Operations Overview is live** at `/operations`, built as a separate UTF-8 module (`frontend/operations.js`) so the mojibake-encoded `pageAdmin` block was never edited. It renders real data only — backend/database/Redis/RQ worker/FFmpeg/disk with a Healthy | Degraded | Offline | **Unknown** vocabulary (never a fake green), render-queue length, running/pending/failed jobs, short/long counts, recent errors (each linking to its fix location) and recent publications — plus loading skeletons, an error state with retry, manual refresh and a last-updated timestamp. Reachable from the main Video Factory navigation. The legacy `/admin` SaaS console is untouched.

Still optional: folding the legacy user/plan/credit console into a "Billing / Users (legacy)" tab, and exposing memory usage + a scheduled-jobs list.
