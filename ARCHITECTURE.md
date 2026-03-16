# AutoSocial.tech Architecture Map

## Main Production Runtime Files
- Frontend: `frontend/app.js`, `frontend/styles.css`, `frontend/index.html`, `frontend/create/index.html`, `frontend/dashboard/index.html`, `frontend/billing/index.html`
- Frontend data/config: `frontend/data/nicheTemplates.js`
- Backend/API: `app.py`, `saas_api.py`, `saas_services.py`, `content_pipeline.py`, `database.py`, `saas_models.py`, `config.py`, `saas_settings.py`
- Plans/billing: `plans_catalog.py`, `services/entitlements.py`, `stripe_service.py`
- Publishing/scheduling: `facebook_api.py`, `worker.py`, `cron_jobs.py`
- Post media: `backend/services/media/pexels_service.py`, `image_picker.py`, `media_query_builder.py`
- Video media/runtime: `footage/providers/pexels.py`, `footage/providers/pixabay.py`, `footage_matcher.py`, `footage/shots.py`, `footage/ranking.py`, `video_pipeline.py`, `video_script_generator.py`, `video/tts.py`, `video/subtitles.py`

## Shared High-Risk Files
- `frontend/app.js`: shared state and rendering for dashboard, create, calendar, history, billing, and admin flows.
- `saas_api.py`: shared route surface for create, planning, campaigns, calendar, publishing, and editor flows.
- `saas_services.py`: business logic used across multiple routes.
- `app.py`: runtime bootstrap, background loops, and scheduling side effects.
- `content_pipeline.py`: central text-generation path.
- `plans_catalog.py`: plan model and gating assumptions used across UI and backend.

## Plans / Billing Area
- `plans_catalog.py`: plan definitions and public plan model.
- `services/entitlements.py`: feature gating and usage decisions.
- `stripe_service.py`: billing integration.
- Billing UI is rendered through `frontend/billing/index.html` and billing logic inside `frontend/app.js`.

## Generation Pipeline
- Post generation: `frontend/app.js` -> `saas_api.py` -> `content_pipeline.py` / `saas_services.py`
- Weekly/monthly planning: `frontend/app.js` -> `saas_api.py` -> persistence/scheduling
- Video generation: `video_pipeline.py`, `video_script_generator.py`, `video/tts.py`, `video/subtitles.py`

## Media Pipeline
- Post images: `backend/services/media/pexels_service.py`, `image_picker.py`, `media_query_builder.py`
- Video media: `footage/providers/pexels.py`, `footage/providers/pixabay.py`, `footage_matcher.py`, `footage/shots.py`, `footage/ranking.py`

## Publishing Flow
- Publishing integration: `facebook_api.py`
- Scheduled execution: `app.py`, `worker.py`, `cron_jobs.py`
- Calendar/history/editor screens are rendered through `frontend/app.js` and backed by `saas_api.py`

## Dashboard / Create Flow
- Dashboard entry points and quick actions live in `frontend/app.js` plus `frontend/dashboard/index.html`
- Create flow and AI director live in `frontend/app.js` plus `frontend/create/index.html`
- Niche-aware behavior depends on `frontend/data/nicheTemplates.js` with matching backend handling in `saas_api.py` / `content_pipeline.py`

## Legacy-Sensitive Boundaries
- `gpt_generator.py`: legacy-sensitive for deprecated GPT image behavior
- `deploy/release/*`: legacy snapshot paths, not default active runtime
- `scripts/verify_release.py`: release verification layer; keep aligned with current runtime markers and contracts

## Critical Domains That Must Not Break
- Auth and session behavior: `saas_auth.py`, API session routes
- Billing and plan enforcement: `plans_catalog.py`, `services/entitlements.py`, `stripe_service.py`
- Publishing/autoposting: `facebook_api.py`, `app.py`, `worker.py`, `cron_jobs.py`
- Dashboard/create/history/calendar state hydration: `frontend/app.js`
- Media relevance and de-duplication: `backend/services/media/pexels_service.py`, `footage/*`