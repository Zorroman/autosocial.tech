# Deployment Hardening & Environment Matrix

This document describes the runtime modes, the environment variables that gate a
safe production configuration, and the fail-closed deployment tooling added under
the production-hardening work. It is documentation only — nothing here deploys,
rotates credentials, or contacts an external service.

Tooling:

| Script | Purpose | Network | Writes |
|---|---|---|---|
| `scripts/validate_production_env.py` | Read-only, fail-closed env validator. Exit 0 only if safe. | none | none |
| `scripts/verify_deployed_frontend.sh` | Verify a deployed `frontend/app.js` (size, SHA-256, UTF-8, markers). SHA passed per-release. | none | none |
| `scripts/deploy_production.sh` | 16-step fail-closed deploy sequence with lock, validated backup, pre-activation frontend integrity, backup-gated migrations, atomic activation, post-activation SHA verify, health/smoke. Honors `DEPLOY_DRY_RUN=1`. | local only in dry-run | backup dir, staged release |

The validator never prints secret values — only `PRESENT` / `MISSING` / `INVALID`
/ `WEAK`, a length, or (at most) the last 4 characters.

## Runtime modes

| Mode | `ENV` | Intent | Providers | Cookies |
|---|---|---|---|---|
| development | `development` (default) | Local dev on SQLite. | Real or mock. | `COOKIE_SECURE=false` OK. |
| test | any (`ENV` unset in pytest) | Isolated per-test app + throwaway SQLite. No network. | Mock / monkeypatched. | n/a |
| production | `production` / `prod` | Single-admin live host. | Real only; mock providers rejected. | `COOKIE_SECURE=true` **required**. |

The app enforces a subset of these at startup (fail-closed): empty admin
allowlist, missing `TOKEN_ENCRYPTION_KEY`, `COOKIE_SECURE=false`, or debug in
production all block boot. `validate_production_env.py` is the pre-deploy gate
that catches the same problems *before* activation.

## Environment matrix

`Secret?` = must live only in the production secret store, never committed.
`Failure` = what happens in **production** when the value is missing/invalid.

### Core / security (production-critical)

| Variable | Required (prod) | Safe default | Failure in production | Secret? |
|---|---|---|---|---|
| `ENV` | yes | `development` | Wrong mode → wrong safety posture. Validator can pin via `--require production`. | no |
| `PRIVATE_ADMIN_MODE` | yes (`true`) | `true` | Not `true` → CRITICAL (product is single-admin). | no |
| `ADMIN_ALLOWLIST_EMAILS` | yes | empty | Empty → **fail closed**, no admin can log in → CRITICAL. | no |
| `COOKIE_SECURE` | yes (`true`) | `false` | `false` in prod → CRITICAL (session cookie over plain HTTP). | no |
| `TOKEN_ENCRYPTION_KEY` | yes | empty | Missing/`<32` chars → CRITICAL (OAuth tokens cannot be encrypted at rest). | **yes** |
| `SECRET_KEY` / `FLASK_SECRET_KEY` | yes | empty | Missing/weak → CRITICAL (session signing). | **yes** |
| `DATABASE_URL` | yes | `sqlite:///autosocial.db` | Missing → CRITICAL. `sqlite` in prod → WARN (use PostgreSQL). | contains creds → **yes** |
| `REDIS_URL` | yes unless `SYNC_JOBS=true` | none | Missing and `SYNC_JOBS` false → CRITICAL (render/upload queue can't run). | no |
| `OPENAI_API_KEY` | variable must exist | empty | Variable absent → CRITICAL (legacy import path). Empty → WARN (AI degraded). | **yes** |
| `USE_MOCK_PROVIDERS` | no | `false` | `true` in prod → CRITICAL (mock media/meta). | no |
| `VISUAL_AI_PROVIDER` | no | `mock` | `mock` while `VISUAL_VALIDATION_ENABLED=true` in prod → CRITICAL. | no |

### YouTube (disabled is a valid production state)

If none of `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `YOUTUBE_REDIRECT_URI`
is set, YouTube is **disabled** and that is OK. If *any* is set, all must be
present and consistent.

| Variable | Required when enabled | Failure in production | Secret? |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | yes | Set without secret → CRITICAL (partial credentials). | no |
| `GOOGLE_CLIENT_SECRET` | yes | Missing while enabled → CRITICAL. | **yes** |
| `YOUTUBE_REDIRECT_URI` | yes | Missing → CRITICAL. localhost redirect in prod → CRITICAL. non-HTTPS in prod → CRITICAL. | no |
| `TOKEN_ENCRYPTION_KEY` | yes | Required whenever YouTube is enabled. | **yes** |

No Google API call is made to validate — consistency is checked structurally.

### Stripe (disabled is a valid production state)

If `STRIPE_ENABLED` is falsey and no `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`
is set, Stripe is **disabled** and that is OK. If enabled:

| Variable | Required when enabled | Failure in production | Secret? |
|---|---|---|---|
| `STRIPE_SECRET_KEY` | yes | Missing → CRITICAL. `sk_test_…` in prod → WARN. | **yes** |
| `STRIPE_WEBHOOK_SECRET` | yes | Empty while enabled → CRITICAL. | **yes** |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` | if set | Non-HTTPS in prod → CRITICAL. | no |

No Stripe API call is made to validate.

### Publishing safety

Auto-publishing is **per-channel and defaults OFF** (`Channel.automatic_publishing_enabled`,
DDL `BOOLEAN DEFAULT 0`). There is no global auto-publish switch. New channels
start disabled; enabling is an explicit user action. Director approve, render,
and OAuth connect never flip the flag. The validator flags any accidental
`AUTOMATIC_PUBLISHING_GLOBAL` / `GLOBAL_AUTO_PUBLISH` override as CRITICAL.

## Secret rotation — required manual action

> **SECURITY:** earlier revisions of `.env.example` (and the legacy
> `deploy/release/.env.example` snapshot) committed a real Stripe **test** secret
> key and webhook secret. Those values remain in Git history. Removing them from
> the current files does **not** remove them from history.
>
> The previously committed Stripe test credentials **must be revoked/rotated
> manually in the Stripe dashboard.** This cannot be done from this repo, and Git
> history is intentionally **not** rewritten here.

`scripts/validate_production_env.py` scans for live/test key prefixes and reports
their presence without printing the value.

## Pre-deploy checklist

1. `python scripts/validate_production_env.py --env-file <prod.env> --require production` → exit 0.
2. Compute the release `frontend/app.js` SHA-256 and pass it to the deploy as `FRONTEND_EXPECTED_SHA`.
3. `DEPLOY_DRY_RUN=1 … scripts/deploy_production.sh` → all 16 steps pass locally.
4. Confirm Stripe test credentials in Git history have been rotated in the Stripe dashboard.
