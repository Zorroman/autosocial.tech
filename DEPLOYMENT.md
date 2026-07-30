# Deployment

This describes how a deploy to the production VPS is actually done — not an
idealized CI/CD diagram, the real procedure, including why it's shaped this way.

## Why it's manual, not GitOps

The production source directory on the VPS is a plain directory, not a git
checkout — a legacy of how the box was originally provisioned, before this
project's current deployment discipline existed. Re-architecting that onto a
GitOps pipeline is a real, worthwhile improvement — and explicitly not done
casually mid-project on a single always-on VPS serving a live, automated
publishing schedule, where an unproven new deploy mechanism carries real risk.
The procedure below is the pragmatic, safety-first alternative: every step is
manual but disciplined, backed by a real backup and rollback path.

## The procedure

1. **Pre-deploy gate.** `scripts/predeploy_check.sh` — working tree must be
   clean, frontend integrity (encoding/mojibake) checked, Python syntax
   checked, the critical test subset run, migrations import-checked.
2. **Full test suite**, run fresh, not reused from a prior run:
   `USE_MOCK_PROVIDERS=true SYNC_JOBS=true python -m pytest tests/ -q`.
3. **Check for in-flight work.** No deploy proceeds while a render/publish job
   is actively running — checked directly (`pipeline_state="running"` count,
   RQ queue depth) immediately before touching anything.
4. **Backup, before any change:**
   - `pg_dumpall` of the live database.
   - A tarball of the current release source.
   - The current Docker image IDs recorded; the current image re-tagged
     (e.g. `autosocial-backend:pre_<change>`) for a one-command rollback.
5. **Ship only what changed.** For a single-file, no-migration fix, only that
   file is copied to the server (with a `sha256` check on both ends) — not a
   full tree sync. For a full release, `git archive HEAD` is extracted over the
   source directory (tracked files only; never touches `.env`, `data/`,
   `output/`, or anything git-ignored).
6. **Rebuild only what needs it.** `backend` and `worker` are independently
   tagged images built from the same Dockerfile — if the changed code is only
   imported by one of them (checked by grepping the actual import graph, not
   assumed), only that service is rebuilt and restarted. The other keeps
   running, mid-render if it's mid-render.
7. **Migrations** run automatically on `backend` startup
   (`run_migrations()` in `app.py`); re-run explicitly and checked for a clean
   exit as part of verification, not assumed successful because the process
   started.
8. **Post-deploy verification** — see below. Rollback is: restore the tagged
   previous image, restart, re-verify. The database backup is never
   auto-restored (migrations are additive; restoring a DB after a
   partially-applied migration is a human decision, not an automated one).

## Post-deploy verification (a real example)

A backend-only fix (no migration, a single changed file) was deployed with this
procedure. What was actually checked, and why the "immediately after restart"
result wasn't trusted at face value:

- Container state: image ID confirmed changed for the touched service; the
  untouched service's container ID, restart count, and start time confirmed
  **unchanged** — proof it was never restarted.
- `/api/health` → 200, `/api/readiness` → `ready`.
- The specific regression the fix targeted was time-dependent (a worker
  heartbeat threshold) — so the check that mattered wasn't the one taken right
  after restart. An explicit **130-second wait** was inserted, then the check
  was repeated: heartbeat age 354 s (was previously misreported as unhealthy
  past 120 s), `/api/readiness` still correctly `ready`. Declaring success from
  the first, too-early reading would have proven nothing.
- Exactly one RQ worker registered (no duplicate registration from the
  restart), queues unchanged (no duplication), scheduler log showed each
  scheduler started exactly once, no new tracebacks in logs.
- Channel settings (publishing mode, daily limits, timezone, visibility)
  compared byte-for-byte against a pre-deploy snapshot — unchanged.
- The live automation kept running *through* the deploy: the project count and
  `last_generated_at` both advanced during the deploy window, and the newly
  auto-published video's URL was independently verified via YouTube's public
  oEmbed endpoint — not just read back from the same database the deploy
  touched.

Full incident narrative in
[`CASE_STUDIES.md`](CASE_STUDIES.md#2-the-worker-was-never-offline) and
[`CASE_STUDIES.md`](CASE_STUDIES.md#5-a-security-incident-found-by-the-tool-built-to-prevent-it).

## What would change this into a real CD pipeline

The honest next step, if this moved to a team: make the VPS source directory an
actual git checkout, add a deploy job to the CI workflow that runs the same
pre-deploy gate and pushes via SSH on a tag, and keep the backup/rollback
discipline exactly as-is — it's already sound, it just isn't triggered by a
pipeline yet.
