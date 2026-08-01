# Production

What's actually running, as of the last verification pass — not aspirational, not
a demo environment.

## Infrastructure

- **Host:** Hetzner CPX22 (2 vCPU, 3.8 GB RAM, no swap), single VPS.
- **Services:** `backend`, `worker`, `postgres`, `redis`, `caddy` — Docker Compose,
  `caddy` handling TLS/reverse-proxy.
- **Uptime discipline:** `postgres`, `redis`, and `caddy` are long-running and
  untouched by application deploys; only `backend`/`worker` images get rebuilt,
  and only the one(s) whose code actually changed (see
  [`DEPLOYMENT.md`](DEPLOYMENT.md)).

## What it actually produces

- **Shorts:** up to 20/day, automated, on a real YouTube channel, published
  inside a configurable daytime window (default 06:00–22:00 local) so nothing
  posts overnight.
- **Long-form:** 1/day, 8–12 minutes, same channel infrastructure, memory-safe
  chunked render (see [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md)).
- **Verified live**, not simulated: real published URLs, independently confirmed
  via YouTube's public oEmbed endpoint (not just a database read) during the
  deployment-verification pass covered in [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Operational safety rails actually in place

- **Idempotent publishing.** A project can't be uploaded to YouTube twice — the
  publish path checks for an existing `youtube_video_id` before starting an
  upload.
- **Self-healing scheduler.** A render killed mid-job (OOM, restart, deploy)
  used to leave a project stuck `pipeline_state="running"` forever, which
  silently blocked *all* further generation on that channel — this actually
  happened in production for ~25 hours before being caught (see
  [`CASE_STUDIES.md`](CASE_STUDIES.md#4-the-scheduler-that-stopped-without-saying-anything)).
  The scheduler now auto-resets anything stuck past a stale-job threshold.
- **Daily-quota reservation is race-safe.** Slot reservation happens inside a
  row-locked transaction (`SELECT ... FOR UPDATE SKIP LOCKED`), so two
  overlapping scheduler ticks can't both claim the same channel's daily slot.
- **Real health data, not a static green light.** The Operations dashboard
  reads actual RQ worker registration, actual Redis/DB connectivity, actual
  FFmpeg/disk state — a value it can't verify is shown as "Unknown", never
  defaulted to healthy.
- **Backups before every deploy.** A Postgres dump and a tarball of the
  previous release's source are taken before any production code change; the
  previous Docker image is tagged for a one-command rollback.

## Known operational limits (stated, not hidden)

- Single point of failure: one VPS, one worker process. Acceptable at current
  volume; the first thing to change if this needed to scale to many channels or
  much higher daily throughput.
- Deployment is manual (SSH-driven), not a GitOps/CD pipeline — see the
  trade-off discussion in [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).
- No multi-region, no CDN in front of rendered video files beyond Caddy —
  not a scale requirement at current traffic.
