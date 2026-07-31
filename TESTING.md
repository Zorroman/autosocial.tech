# Testing

## Unit / integration — pytest

```bash
USE_MOCK_PROVIDERS=true SYNC_JOBS=true python -m pytest tests/ -q
```

269 tests. Every AI provider call and every YouTube call is mocked or run in a
sandboxed/sync mode — the suite never spends real API budget and never touches a
real YouTube channel. `SYNC_JOBS=true` runs jobs inline instead of via Redis/RQ,
so the suite needs no running Redis.

Coverage includes: auth flows, channel/project CRUD, the full script→scenes→
media→render→publish pipeline (mocked at the provider boundary), scheduler
reservation and self-heal logic, footage cooldown/reservation, dashboard data
shape (including that it never surfaces fabricated social metrics), and targeted
regression tests for bugs found during hardening (see below).

Runs in CI on every push/PR: [`.github/workflows/tests.yml`](.github/workflows/tests.yml).

## Regression tests for real bugs, not hypothetical ones

A few worth pointing at directly, because they encode an actual incident rather
than a generic "test the happy path":

- `test_worker_status_stale_heartbeat_but_registered_is_online` /
  `test_worker_status_expired_registration_is_offline`
  (`tests/test_factory_dashboard.py`) — a worker whose last heartbeat is 300
  seconds old must still report `online`; one whose registration has genuinely
  expired must not. This is the exact shape of the false "Worker Offline" bug
  (see [`CASE_STUDIES.md`](CASE_STUDIES.md#2-the-worker-was-never-offline)) —
  the test fails on the old threshold-based logic and passes on the fix.
- `test_output_url_is_null_when_rendered_file_is_missing`
  (`tests/test_video_projects.py`) — a project whose `output_path` is set but
  whose file is gone must not get a playable URL back. Written after finding
  this live in a browser (an empty `<video>` player, a dead download link).
- `test_scheduler_reservation_blocks_double_generation`
  (`tests/test_media_matcher.py`) — asserts the row-lock reservation actually
  prevents two concurrent scheduler ticks from claiming the same channel's
  daily slot.
- `test_dashboard_short_long_split` — the dashboard's short/long video counts
  sum to the actual project count; a real assertion against real data shape,
  not a snapshot test.

## Security regression: CI-gated secret scanning

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs `gitleaks` on
every push/PR. This exists because a pre-publication manual scan found real
credentials in this repository's git history (full incident in
[`SECURITY.md`](SECURITY.md)) — the CI job is there so that class of mistake
can't quietly land again.

## Static analysis: ruff

`make lint` / `ruff check .` (config in `pyproject.toml`) catches unused
imports, unused variables, redefined names, and undefined names. It found —
and a follow-up pass fixed — a real unconditional `NameError` in a fallback
code path (see [`CASE_STUDIES.md`](CASE_STUDIES.md)) and ~460 lines of
unreachable dead code from an abandoned scoring implementation. Runs as its
own CI job in [`.github/workflows/tests.yml`](.github/workflows/tests.yml)
alongside `pytest` and `gitleaks`. The rule set is deliberately narrow for
now (see `pyproject.toml`'s comment) — this codebase had zero lint tooling
before this pass, so style rules (import order, line-length nits) are a
separate, later step rather than something to turn on and immediately
enforce in the same change.

## Browser-level verification

- **E2E (Playwright)**, driving real critical flows: `tests/e2e/`.
- **Responsive + console sweep** — a scripted check (not a manual eyeball pass)
  across 10 pages × 4 viewports (375×812, 768×1024, 1024×768, 1440×900),
  asserting `document.documentElement.scrollWidth <= window.innerWidth` and
  zero console errors on every combination. It caught a real layout bug: a CSS
  grid without `minmax(0, 1fr)` caused horizontal overflow at exactly 1024px on
  three pages. Fixed and re-verified: 0/40.
- **Manual browser walkthrough** of every pipeline state (completed,
  processing, failed, published) for the Video Details view — this is what
  surfaced the missing-file `output_url` bug above; a scripted DOM check alone
  wouldn't have shown the visibly broken player.

## Local dev tooling built for testability

- `scripts/dev-start.sh` — boots a fully isolated local stack (mock AI
  providers, an isolated SQLite DB, `SYNC_JOBS=true`, no Redis/worker
  dependency) so the app can be exercised end-to-end without touching
  production or spending API budget.
- `scripts/dev_frontend_server.py` — a minimal SPA-fallback static server for
  local dev, so deep links (`/projects/12`, `/operations`) work the same way
  the production reverse proxy serves them, instead of 404ing under a plain
  `python -m http.server`.

## What isn't covered (stated honestly)

- No load/performance test suite — traffic volume doesn't currently justify one.
- No mutation testing or formal coverage-percentage gate — test additions have
  been driven by real bugs found, not a coverage target.
- `frontend/app.js` has no unit-test harness of its own (no JS test runner in
  the project); its correctness is exercised through the Playwright E2E and
  browser-console sweep instead of isolated unit tests.
