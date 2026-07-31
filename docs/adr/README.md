# Architecture Decision Records

Short records of decisions that shaped this system, written so a reader can
evaluate the trade-off, not just the outcome. These are retrospective — written
to document real decisions already made in the codebase — not a process that
was run formally at the time.

| ADR | Decision |
|---|---|
| [ADR-001](001-why-docker.md) | Why Docker (Compose, not Kubernetes) |
| [ADR-002](002-why-redis-queue.md) | Why Redis as the job queue backend |
| [ADR-003](003-why-rq.md) | Why RQ, not Celery |
| [ADR-004](004-why-ffmpeg.md) | Why FFmpeg subprocess, not a Python video library |
| [ADR-005](005-why-polling.md) | Why polling loops, not cron or a task scheduler framework |
| [ADR-006](006-why-youtube-first.md) | Why the product pivoted to YouTube-first |

Related: [`ENGINEERING_DECISIONS.md`](../../ENGINEERING_DECISIONS.md) covers
product/frontend decisions (vanilla JS, auth model, legacy code retention)
that are lower-level than an ADR but follow the same defend/wouldn't-defend
framing.
