# Roadmap

Known, scoped next steps — not a promise of a release schedule (this project
doesn't run one; see [`CHANGELOG.md`](CHANGELOG.md)). Each item below is
already named as a real, disclosed limitation somewhere else in the docs;
this page just collects them in one place with a rough priority.

## Near-term (would do next if this scaled up)

- **Containerize the actual production host.** The live server predates
  Docker and is deployed via a manual SSH procedure
  ([`DEPLOYMENT.md`](DEPLOYMENT.md)); `docker-compose.yml` already defines
  the target topology ([ADR-001](docs/adr/001-why-docker.md)) but isn't what
  runs in production yet. Converting mid-flight on a live single-VPS system
  with no staging environment was judged too risky to do opportunistically —
  this is the natural next step once a staging environment exists to
  validate against.
- **Tag-triggered CD on top of the same deploy discipline.** The manual
  procedure already has the right gates (tests, in-flight-job check, backup,
  health-verified rollback) — see "What would change this into a real CD
  pipeline" in [`DEPLOYMENT.md`](DEPLOYMENT.md). Automating the trigger is
  lower-risk than automating the safety checks themselves, which already
  exist.
- **Fix the character-encoding corruption**, both in the legacy admin block
  in `frontend/app.js` (recoverable mis-decoded bytes) and in several backend
  files (`saas_api.py`, `dashboard_metrics.py`, `video_niches_config.py`,
  where the original characters were destroyed, not just misdecoded). Done
  as its own isolated, tested change rather than worked around or guessed
  at again — see [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md) for
  why this wasn't safe to fix inline as part of an unrelated change.

## Medium-term (real work, not currently justified by volume)

- **Split `frontend/app.js` by route/feature** using native ES modules
  (still no build step). At ~19,000 lines it's the single biggest
  maintainability ceiling in the codebase — flagged directly in
  [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md) as something not
  worth repeating.
- **Load testing against the API/DB layer.** Never done, because the system
  has never been near its actual ceiling (one render worker, ~20 Shorts +
  1 long-form video/day). Worth doing before any claim about scaling
  further is made — see [`PERFORMANCE.md`](PERFORMANCE.md).
- **A second, independent render worker** (own VPS, own queue namespace) if
  daily volume or channel count grows enough that a single worker becomes
  the real bottleneck — not before, since the current single-worker design
  is what guarantees renders never overlap and OOM the box
  ([ADR-002](docs/adr/002-why-redis-queue.md)).

## Explicitly not planned

- **Multi-platform publishing generalization** (fan-out to Instagram Reels/
  TikTok from the same pipeline). The product is deliberately YouTube-first
  right now — see [ADR-006](docs/adr/006-why-youtube-first.md) for the
  reasoning and what would need to change first.
- **Deleting the legacy Meta/Stripe posting surface.** It's real, working
  code someone still relies on; removing it is a product decision, not
  something to do as incidental cleanup — see "Keeping legacy code paths"
  in [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).
