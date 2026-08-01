# ADR-001: Docker Compose, not Kubernetes

## Context

The system needs five coordinated processes in production: a Flask API, an
RQ worker, Caddy (reverse proxy + TLS), PostgreSQL, and Redis. It runs on a
single Hetzner CPX22 VPS (3.8 GB RAM, no swap) with one operator. There is no
multi-node requirement: throughput is bounded by a single render worker by
design (see [ADR-002](002-why-redis-queue.md)), so horizontal pod scaling
would not increase capacity.

## Decision

Run all five services via a single `docker-compose.yml`, deployed with
`docker compose up -d --build`. Migrations run automatically on backend
startup (`run_migrations()` in `app.py`), so bringing the stack up is a
one-command bootstrap.

## Alternatives considered

- **Kubernetes (k3s or managed).** Rejected: the cluster control plane alone
  would consume a meaningful fraction of 3.8 GB RAM, for a workload that is
  architecturally single-node (one render worker, no horizontal scaling
  target). It would add real operational surface — manifests, ingress
  controller, secrets management — with no corresponding capacity gain.
- **Bare-metal systemd services, no containers.** This is in fact how the
  actual production host runs today (see [DEPLOYMENT.md](../../DEPLOYMENT.md)
  — the production source directory predates containerization and deploys via
  a disciplined manual SSH procedure, not `docker compose`). Docker Compose is
  the reproducible, portable path — it's what a reviewer or a new operator
  runs locally, and what a future migration to a proper host would adopt —
  but it is not (yet) how the live system is actually deployed.
- **Nomad / Docker Swarm.** Rejected as unnecessary complexity for a
  single-node deployment; Compose already expresses the five-service topology
  clearly.

## Trade-offs

- Compose has no built-in rolling deploy, health-gated restart, or
  multi-host scheduling. Accepted — a single node doesn't need them, and
  `DEPLOYMENT.md` implements the equivalent safety (backup, health check,
  rollback) as an explicit script rather than a platform feature.
- The gap between "how you'd run this from scratch" (Compose) and "how
  production actually runs today" (manual/systemd) is a real, disclosed
  inconsistency — see [ENGINEERING_DECISIONS.md](../../ENGINEERING_DECISIONS.md)
  for why converting the live host wasn't done opportunistically.

## Consequences

- `docker compose up -d --build` is the correct, complete way to evaluate or
  develop against this system — no undocumented manual setup steps.
- Migrating production to containers is a scoped, known future step, not a
  surprise: the compose file already defines the target topology.
