# Contributing

This is a solo portfolio project, published under a
[proprietary, portfolio-only license](LICENSE) — it is not accepting code
contributions, and the license doesn't grant permission to copy, modify, or
redistribute the code. This file exists anyway because a reviewer opening it
should get a straight answer, not a 404.

## If you're an interviewer or reviewer

The most useful thing you can do is point at something specific:

- **Found a bug, an inaccuracy in the docs, or something that doesn't match
  what the code actually does?** Open an issue. That kind of feedback is
  genuinely useful and will get read.
- **Want to ask about a design decision?** Check
  [`docs/adr/`](docs/adr/) and [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md)
  first — the reasoning (and what I'd do differently) is usually already
  written down. If it isn't, that's worth an issue too.
- **Want to see how a real bug got fixed here?** See
  [`CASE_STUDIES.md`](CASE_STUDIES.md) for full incident write-ups, not just
  outcomes.

## If you're evaluating the code style / conventions

- Backend: Python, Flask, SQLAlchemy. See [`TESTING.md`](TESTING.md) for how
  changes are verified (`python -m pytest tests/ -q`) and
  [`CLAUDE.md`](CLAUDE.md) for the working conventions used on this repo
  (scope discipline, shared-file blast-radius rules).
- Frontend: vanilla JS, no build step. See the "Vanilla JS SPA" decision in
  [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md) for why, and what I'd
  change about it on a team codebase.

## Reporting a security issue

Do not open a public issue for a security vulnerability. See
[`SECURITY.md`](SECURITY.md) for how to report one privately, and for the
disclosed history of the one real security incident this project already
had (a secrets-in-git-history leak, found and fixed pre-publication).
