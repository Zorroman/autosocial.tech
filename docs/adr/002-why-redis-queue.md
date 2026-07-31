# ADR-002: Redis as the job queue backend

## Context

Video rendering (Shorts and long-form) and other slow operations (script
generation, media fetch) can't run inline in an HTTP request — a render takes
minutes, not milliseconds. The API needs to hand work off to a background
process and track its state (queued → running → done/failed) from the
dashboard. The whole system already runs on a single 3.8 GB VPS with no
existing message broker.

## Decision

Use Redis as the queue backend (via RQ — see [ADR-003](003-why-rq.md)), with
a single shared `render` queue consumed by one worker process
(`worker.py`). `SYNC_JOBS=true` is available as a synchronous fallback for
tests and local dev without Redis running (see `tests/` and
`docker-compose.yml`).

## Alternatives considered

- **PostgreSQL as a queue (`SELECT ... FOR UPDATE SKIP LOCKED`).** Viable and
  would remove a dependency, but Redis was already the natural choice given
  RQ's design, and Redis's in-memory operations are simpler to reason about
  for the queue's actual access pattern (enqueue, dequeue, heartbeat) than
  hand-rolled row-locking SQL.
- **RabbitMQ / Kafka.** Rejected as disproportionate: this system has one
  producer type (the API), one consumer (the worker), and no need for
  multi-consumer fan-out, exactly-once delivery guarantees, or a durable
  event log. A broker built for those guarantees adds operational surface
  (another service to run, monitor, and fit into 3.8 GB) without a matching
  requirement.
- **No queue — synchronous generation in the request.** Rejected outright:
  renders take minutes; an HTTP request can't block that long, and a crashed
  request would silently lose the job with no retry state.

## Trade-offs

- Redis holds queue state in memory; a Redis restart without persistence
  configured would lose in-flight job metadata. Mitigated by keeping renders
  resumable at the chunk level (see
  [SYSTEM_DESIGN.md](../../SYSTEM_DESIGN.md)) rather than depending on the
  queue itself for crash recovery.
- Redis is one more process sharing the 3.8 GB RAM budget. Accepted — its
  footprint is small relative to a render process, and it's already required
  for session/rate-limit state elsewhere in the app.

## Consequences

- Job state (queued/running/failed) is queryable from Redis via RQ's own
  `Worker.all()` / job registries, which is what the Operations dashboard
  and the worker heartbeat health check ([CASE_STUDIES.md](../../CASE_STUDIES.md#2-the-worker-was-never-offline))
  read directly, instead of maintaining a second, parallel status table.
