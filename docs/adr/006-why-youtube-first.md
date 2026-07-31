# ADR-006: YouTube-first, not multi-platform-first

## Context

The project started as a broader social-media SaaS tool: post generation and
scheduling across Facebook and Instagram via the Meta Graph API, with billing
and multi-tenant plan tiers. That surface still exists and still works (see
[ENGINEERING_DECISIONS.md](../../ENGINEERING_DECISIONS.md#keeping-legacy-code-paths-instead-of-deleting-them-outright)).
The product's primary positioning has since moved to fully automated
YouTube video production: script → voiceover → footage/music → subtitles →
render → publish, for Shorts and long-form, running on a schedule with no
manual step.

## Decision

Build the video pipeline, scheduler, and Operations dashboard around YouTube
as the single publishing target, rather than generalizing to a
platform-agnostic "publish anywhere" abstraction across Meta and YouTube.

## Alternatives considered

- **A unified multi-platform publishing abstraction** (one video pipeline,
  fan-out to YouTube + Instagram Reels + TikTok). Rejected for this phase:
  each platform has different aspect ratio, length, and metadata
  constraints, and building a correct abstraction across three publishing
  APIs before validating the pipeline against even one was judged higher
  risk than shipping YouTube-only first and generalizing later if warranted.
- **Retrofitting the existing Meta/Facebook posting code to also carry
  video.** Rejected: that surface was built for image/text posts on a
  scheduling cadence (`Channel.automatic_publishing_enabled`, per-channel,
  default off), not for a memory-constrained render pipeline with its own
  worker/queue lifecycle (see [ADR-002](002-why-redis-queue.md)). Bolting
  video rendering onto the old post-scheduling code path would have coupled
  two systems with genuinely different reliability requirements.
- **Deleting the legacy Meta/Stripe surface outright** when repositioning.
  Rejected as a unilateral call that shouldn't be made silently as a side
  effect of a positioning change — it's real, working code that predates
  this phase; see the linked engineering decision for the full reasoning.

## Trade-offs

- The codebase now visibly carries two eras' worth of naming and structure
  at once — `models.py` alongside `saas_models.py`, a legacy Post Studio
  next to Content Director. This is a real, disclosed cost of not deleting
  the old surface (see the linked decision), not hidden from a reviewer.
- Product-market decisions specific to YouTube (Shorts vs. long-form
  duration targets, subtitle/caption conventions, publish scheduling
  cadence) are baked into the pipeline rather than expressed as
  platform-configurable parameters. Revisiting multi-platform support later
  means generalizing these, not just adding a new API client.

## Consequences

- The render pipeline, scheduler pacing (~48 min/Shorts slot, one long-form
  video/day), and Operations dashboard are all designed and tuned against
  YouTube's actual constraints and quota behavior, not a lowest-common-
  denominator abstraction.
- Any future platform expansion is a deliberate, scoped decision — not a
  path already half-built and left inconsistent.
