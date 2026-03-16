---
name: frontend-flow-fix
description: Repair an AutoSocial.tech frontend flow with minimal edits, stable contracts, and explicit blast-radius awareness.
---

# Frontend Flow Fix

## Default Scope
- `frontend/app.js`
- `frontend/styles.css` only if layout/state styling truly requires it

## Workflow
1. Identify the exact broken state transition.
2. Find the render block and handler in `frontend/app.js`.
3. Trace the matching backend route if behavior is not purely local.
4. Patch the minimum state/render/action logic.
5. Verify render, API payload, success state, error state, and stale-state cleanup.

## Guardrails
- Do not create a second parallel flow.
- Do not broaden scope without justification.
- Do not touch shared backend files unless the frontend fix truly depends on them.
- Do not reintroduce GPT image behavior into media flows.

## Output
1. Runtime path
2. Files changed
3. State/event changes
4. Verification