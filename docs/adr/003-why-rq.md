# ADR-003: RQ, not Celery

## Context

Once Redis was chosen as the queue backend ([ADR-002](002-why-redis-queue.md)),
a Python queue library was needed to define jobs, run a worker, and expose
job/worker state to the app. The workload is simple: one job type family
(render/generate), one queue, one worker process, no complex routing, no
scheduled/periodic task graph beyond what a couple of `time.sleep` loops
already handle (see [ADR-005](005-why-polling.md)).

## Decision

Use RQ (`rq==2.10.0`). `worker.py` runs `rq.Worker`; jobs are plain Python
functions enqueued onto a single `render` queue.

## Alternatives considered

- **Celery.** The default choice for Python task queues, and capable of
  everything here and far more (multiple brokers, complex routing, Celery
  Beat for periodic tasks, canvases/chords for job graphs). Rejected because
  none of that is needed: Celery's configuration surface (broker transport
  options, result backend, worker pool models, Beat scheduling) is overhead
  for a single queue and a single worker. RQ's entire API surface is close to
  "enqueue a function, get a job back" — which is what this system actually
  does — and it made the worker heartbeat bug (see
  [CASE_STUDIES.md](../../CASE_STUDIES.md#2-the-worker-was-never-offline))
  tractable to root-cause by reading RQ's small, readable source directly
  rather than tracing through a much larger framework.
- **Dramatiq.** A reasonable, simpler alternative to Celery; not chosen
  mainly because RQ's Redis-native, minimal-dependency model fit the existing
  Redis-only infrastructure most directly, with no separate broker
  abstraction layer to configure.

## Trade-offs

- RQ has weaker built-in support for complex workflows (chained/grouped
  jobs) than Celery. Not a real cost here — the render pipeline's stages run
  sequentially inside one job function, not as a graph of separate queued
  tasks.
- RQ's liveness model (`worker_ttl`, refreshed on each dequeue poll) has to
  be understood correctly by anything monitoring worker health, or a
  misconfigured health check will produce false "offline" alerts — which is
  exactly what happened in production; see the case study linked above.

## Consequences

- Worker health is derived from RQ's own `Worker.all()` registration state,
  not a separately maintained heartbeat table.
- Adding a genuinely complex job graph in the future (e.g. fan-out across
  multiple render workers) would likely mean revisiting this decision —
  RQ was chosen for the workload as it exists today, not as a bet that it
  never changes.
