# AutoSocial.tech Regression Checklist

## Frontend Checks
- `frontend/app.js` change is limited to the intended flow.
- No stale state between niche change, topic change, and preview/result blocks.
- Calendar/history/editor screens still render and save expected state.

## Product Flow Checks
- Dashboard -> create -> generate flow still reaches the intended mode and returns a usable result.
- Weekly plan flow still supports form input, plan generation, preview, and scheduling.
- Monthly plan flow still supports generation/preview if the task touches planning logic.
- Publish flow still works for manual publish and scheduled publish if the task touches calendar, editor, or backend scheduling.
- Video flow still works when the task touches shared create state, media state, or route contracts.

## Backend Checks
- Affected API routes still return the same contract shape unless the task explicitly changes it.
- `saas_api.py` and `saas_services.py` remain aligned with frontend expectations.
- Background jobs or schedulers in `app.py`, `worker.py`, and `cron_jobs.py` are not accidentally widened or disabled.
- No deprecated runtime path is reactivated.

## API Contract Checks
- Route names unchanged unless task explicitly requires a migration.
- Response fields and status codes remain stable for existing consumers.
- Query params, body fields, and persisted meanings remain backward compatible.

## Plan Enforcement Checks
- Check entitlements against `plans_catalog.py` and `services/entitlements.py`.
- Do not introduce UI states that bypass backend plan enforcement.
- Verify trial/starter/growth/agency gating if the task touches create, dashboard, billing, scheduling, or publishing.

## Legacy Path Checks
- Search for reactivation of legacy image/runtime behavior:
  - `rg -n "generate_image_url|images.generate|gpt-image|client.images"`
  - `rg -n "deploy/release"`
- Confirm no active runtime path depends on deprecated GPT image logic.

## Media / Repetition Checks
- For post media, verify no repeated fallback image pattern across a batch when avoidable.
- For video media, verify no repeated generic footage across scenes when the task touches footage logic.
- Confirm niche/topic relevance still outweighs generic stock fallback.

## Suggested Smoke Targets
- `tests/test_ai_director.py`
- `tests/test_content_generation.py`
- `tests/test_pexels_service.py`
- `tests/test_entitlements.py`
- `tests/test_saas.py`
- `tests/test_video_pipeline.py`
- `scripts/verify_release.py`