# AutoSocial.tech Codex Guide

## Repo Summary
- AutoSocial.tech is an AI Video Factory: it generates scripts, voiceover, footage/music, subtitles, and renders short (Shorts) and long-form videos, then publishes them to YouTube automatically. A legacy social-media posting/billing surface (Facebook/Instagram, Stripe plans) from an earlier product scope still exists and still works — see `ENGINEERING_DECISIONS.md` for why it wasn't deleted — but it is not the primary product.
- Frontend production runtime is centered in `frontend/app.js` with page shells under `frontend/*/index.html`.
- Backend/API production runtime is centered in `api.py`, `app_services.py`, `app.py`, `content_pipeline.py`, and `plans_catalog.py`.
- Post media routes through `backend/services/media/pexels_service.py` and must not reintroduce GPT image generation.

## Core Rules
- Preserve backward compatibility unless the task explicitly authorizes a contract break.
- Prefer minimal targeted edits over broad refactors.
- Reuse existing patterns before introducing new abstractions.
- If a task can be solved in `1-3` files, do not expand scope.
- Keep API contracts stable across frontend, backend, and scheduled jobs.

## Hard Constraints
- Never reintroduce deprecated GPT image generation into production runtime paths.
- Do not break auth, billing, plans, publishing, onboarding, dashboard, create flow, weekly/monthly planning, or generation flows.
- Do not widen plan entitlements or feature access unless the task explicitly requires it.
- Do not silently change route shapes, response payloads, query params, or persisted field meanings.
- Avoid repeated media and repeated footage fallbacks; prefer deterministic de-duplication over random retries.
- Treat `deploy/release/*` as legacy unless the task explicitly targets legacy snapshots.
- Broad refactors are forbidden unless the task directly asks for a refactor.

## Mandatory Execution Order
1. Inspect the exact runtime path first.
2. Write a concrete plan before editing.
3. Edit the minimum file set.
4. Verify changed behavior and adjacent domains.

Do not skip planning when touching shared runtime files.

## Scope Discipline
- Start with the smallest real file scope that can solve the task.
- If more than `3` files must change, explicitly justify why the smaller scope is insufficient.
- Expand scope only if inspection or verification proves the initial fix is incomplete.
- Avoid speculative cleanups in unrelated domains while solving a focused issue.
- Report untouched but potentially affected adjacent domains in the final response.

## Shared High-Risk Files
- `frontend/app.js`
- `api.py`
- `app_services.py`
- `app.py`
- `content_pipeline.py`
- `plans_catalog.py`

When touching any of these:
- state the blast radius before editing
- explain why the change belongs in that shared file
- verify the adjacent product flows most likely to regress

## Frontend Rules
- Primary frontend runtime file: `frontend/app.js`.
- Keep page behavior aligned with existing shells such as `frontend/index.html`, `frontend/create/index.html`, `frontend/dashboard/index.html`, and `frontend/billing/index.html`.
- Avoid UI-only fixes that leave backend state or route behavior inconsistent.
- Preserve existing query-param and state hydration patterns for dashboard/create flows.
- Do not add decorative UI states that are not backed by working behavior.

## Backend Rules
- Primary backend runtime files: `api.py`, `app_services.py`, `app.py`, `content_pipeline.py`, `plans_catalog.py`.
- Preserve plan enforcement and entitlements behavior defined in `plans_catalog.py` and `services/entitlements.py`.
- Media/image changes must stay aligned with `backend/services/media/pexels_service.py`, `image_picker.py`, and persisted media handling.
- Do not break publishing integrations in `facebook_api.py` or scheduled execution paths in `app.py`, `worker.py`, or `cron_jobs.py`.

## Verification Mindset
- Assume regressions are possible until checked.
- Verify both product behavior and contract stability.
- For frontend changes, validate create/dashboard/history/calendar paths if affected.
- For backend changes, validate route behavior, plan enforcement, and scheduled/publishing side effects if affected.
- For media changes, check for duplicate fallback behavior and legacy runtime reactivation.
- For shared-file edits, always verify untouched but adjacent domains.

## Required Response Format
1. Solution summary
2. Files changed
3. Why this file scope was necessary
4. Verification performed
5. Untouched but potentially affected domains
6. Risks or assumptions