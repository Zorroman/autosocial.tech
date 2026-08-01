# ADR-005: Polling loops, not cron or a task scheduler framework

## Context

Two things need to happen on a schedule with no human trigger: Shorts get
generated roughly every ~48 minutes (about 20/day) on one channel, and one
long-form video gets generated daily on another. Both need to check
real-time state (is a render already running? is it this channel's turn?)
before acting, not just fire blindly on a timer.

## Decision

Run two long-lived Python processes (`scheduler.py` for Shorts,
`longform_scheduler.py` for long-form), each a simple loop:
`time.sleep(interval)`, check state, act if appropriate, repeat. No cron,
no Celery Beat, no APScheduler.

## Alternatives considered

- **OS cron.** Rejected: cron fires blindly on a wall-clock schedule with no
  awareness of in-flight state. This system's core safety property — never
  let two memory-hungry renders overlap and OOM the box (see
  [ADR-002](002-why-redis-queue.md) and
  [SYSTEM_DESIGN.md](../../SYSTEM_DESIGN.md)) — requires checking "is
  anything running right now?" immediately before acting, which a stateless
  cron trigger can't express without an external lock anyway. A cron job
  that shells out to a state-checking script ends up reimplementing the same
  loop, just split across two processes and a crontab entry.
- **Celery Beat / APScheduler.** Would add a scheduling framework and its own
  persistence/coordination model for two loops that are each a handful of
  lines. Rejected as disproportionate — the same reasoning as
  [ADR-003](003-why-rq.md): the workload doesn't have the complexity
  (multiple periodic tasks with different cron expressions, distributed
  scheduler coordination) that these frameworks exist to solve.
- **Database-driven scheduling with a leader-election lock.** Considered for
  the case where the scheduler runs on multiple nodes — but this system is
  intentionally single-node (see [ADR-001](001-why-docker.md)), so
  leader election would be solving a problem that doesn't exist yet.

## Trade-offs

- A polling loop's timing precision is bounded by its sleep interval, not
  exact-to-the-second like cron. Irrelevant here — a Shorts slot landing a
  few seconds early or late has no product impact.
- If the scheduler process itself dies silently, nothing else notices unless
  something else is watching for it — which is exactly what happened once in
  production. See
  [CASE_STUDIES.md #4](../../CASE_STUDIES.md#4-the-scheduler-that-stopped-without-saying-anything)
  for the real incident and the self-heal check that was added afterward
  specifically because a bare polling loop has no built-in "I'm alive"
  signal the way a cron-triggered job at least implies (the last run
  timestamp) — remembered in ongoing session notes as the
  ["Shorts stuck-running outage"](../../CASE_STUDIES.md#4-the-scheduler-that-stopped-without-saying-anything)
  pattern to check first whenever generation silently stops.

## Consequences

- Both schedulers are simple enough to read start-to-finish in one sitting —
  a deliberate trade against the richer feature set a scheduling framework
  would bring, made because that richer feature set has no current use here.
- Detecting "the scheduler process died" required adding an explicit
  liveness/self-heal check rather than getting one for free from the
  polling design — a known, accepted gap that a framework-based scheduler
  might have narrowed, at the cost of everything above.
