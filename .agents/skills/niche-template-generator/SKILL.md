---
name: niche-template-generator
description: Safely add or extend a niche in AutoSocial.tech without creating parallel configs or weak generic content.
---

# Niche Template Generator

## Edit Surface
- `frontend/data/nicheTemplates.js`
- `backend/services/media/pexels_service.py` only if media vocabulary needs support
- `frontend/app.js` only if an existing caller truly requires a new field

## Workflow
1. Add the niche to the existing source of truth.
2. Keep topics, hooks, CTA, offers, and banned words complete.
3. Add media vocabulary only if image relevance would otherwise be weak.
4. Verify selector, suggestions, weekly usage, and hashtag quality.

## Rules
- Do not add a label-only niche.
- Do not introduce generic marketing filler.
- Do not hardcode the niche in multiple places if the config should drive it.
- Do not allow cross-niche leakage in topics, tags, or media vocabulary.

## Output
1. Files changed
2. Fields added
3. Media relevance updates
4. Validation run