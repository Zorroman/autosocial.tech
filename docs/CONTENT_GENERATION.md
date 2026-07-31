# Content Generation Pipeline

## Overview

New API flow generates and stores:

- `content_briefs`
- `content_strategies`
- `content_drafts`

Generation is a 2-step pipeline:

1. `STRATEGY` JSON
2. `DRAFTS` JSON per platform and variant

OpenAI config:

- `OPENAI_API_KEY` (required for real GPT)
- `OPENAI_MODEL` (optional, default from `app_settings.py`)
- `OPENAI_TIMEOUT_SECONDS` (optional)

If `USE_MOCK_PROVIDERS=true` or key is missing, service uses deterministic mock output.

## Endpoints

- `POST /api/content/generate`
- `GET /api/content/briefs?limit=20`
- `GET /api/content/briefs/{id}`
- `POST /api/content/drafts/{id}/save`
- `POST /api/content/drafts/{id}/schedule`
- `POST /api/content/drafts/{id}/publish`

## Notes

- Do not log prompts with secrets or API keys.
- JSON output is validated. One auto-retry is used if JSON is invalid.
- Schedule/publish reuses existing post creation and publish flows.
