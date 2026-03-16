---
name: release-audit
description: Audit an AutoSocial.tech change for legacy reactivation, API or UI mismatch, plan drift, repeated fallback behavior, dead UI states, and unintended route exposure.
---

# Release Audit

## Check First
- `frontend/app.js`
- `saas_api.py`
- `saas_services.py`
- `plans_catalog.py`
- `services/entitlements.py`
- `backend/services/media/pexels_service.py`

## Workflow
1. Trace the exact UI -> state -> API -> persistence path.
2. Run targeted searches:
   - `rg -n "deploy/release|generate_image_url|images.generate|gpt-image|client.images"`
3. Compare frontend payloads vs backend responses.
4. Check adjacent gating/publishing/media behavior only where the shared file demands it.
5. Report the smallest safe fix scope.

## Always Flag
- legacy runtime reactivation
- UI/API contract mismatch
- plan enforcement drift
- repeated media or repeated fallback footage
- route exists but is not part of the real flow

## Output
1. Runtime path
2. Files inspected
3. Findings by severity
4. Minimal fix scope
5. Verification gaps