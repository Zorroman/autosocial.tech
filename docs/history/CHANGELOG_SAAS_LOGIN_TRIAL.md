# SaaS Login Trial Hotfix — Russian login, Free Trial CTA, TIMESTAMP migration fix

- Release date: 2026-06-20
- Deployed commit: `e168587`
- Production target: `https://autosocial.tech` and `https://api.autosocial.tech`
- Active source path: `/opt/autosocial/src`

## What Shipped

- Kept `/login` Russian when the application shell language is `ru`, including browsers with a German locale.
- Restored the email and password fields removed by a broken conditional fragment.
- Removed the visible `? 'без лимита'` fragment from the registration form.
- Kept Free Trial signup independent from Stripe checkout.
- Persisted PostgreSQL-safe `TIMESTAMP` handling for legacy `DATETIME` migration definitions.
- Preserved backend paywall enforcement and existing plan entitlements.

## Live Verification

- API health: `200`
- `/login`: `200`
- Russian registration title and helper text: PASS
- Email and password fields visible: PASS
- German `Konto erstellen` absent: PASS
- Broken conditional text absent: PASS
- Free Trial CTA opens registration and sends no Stripe checkout request: PASS
- Backend healthy and worker listening: PASS

## Rollback Note

Deployed files:

- `/opt/autosocial/src/frontend/app.js`
- `/opt/autosocial/src/frontend/login/index.html`
- `/opt/autosocial/src/migrations.py`

Backup:

- `/opt/autosocial/backups/e168587_20260620_225837`

Release archive:

- `/tmp/release_e168587_saas_hotfix.tar.gz`
- SHA256: `b11e7363cbe5ef69b4b729c24622c9a7ff3c91a844a934bbd1f652ffc3200ae6`

Rollback restores the three backed-up files into `/opt/autosocial/src`, then rebuilds and recreates only the `backend` and `worker` services. Caddy does not require a restart because frontend files are bind-mounted.

## Final Verdict

The SaaS login/trial hotfix is deployed, live-smoke verified, and safe to keep live.
