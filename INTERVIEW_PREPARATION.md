# Interview Preparation

Questions an interviewer is likely to ask about this project, with the answer
I'd actually give — not a link to a doc, the spoken version. Where a doc has
the full depth, I point to it, but the answer here stands on its own.

## "Walk me through the architecture."

Five Docker Compose services on one VPS: Flask API, one RQ worker (running
both the render jobs and two in-process schedulers), Postgres, Redis, Caddy
in front. The interesting constraint is the box: 3.8 GB RAM, no swap, and it
renders real 1080p video. Almost every non-obvious decision in this codebase
traces back to that one number. See `docs/diagrams/system-architecture.svg`
and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## "Why does the render never OOM on such a small box?"

Because it never holds more than one segment in memory. Early on, one giant
FFmpeg `filter_complex` graph over the whole timeline OOM-killed the worker at
~40% progress on any video over a few minutes — that's not a tuning problem,
it scales with length. The fix: one short FFmpeg process per segment, grouped
into chunks with a stream-copy concat (no re-encode), `ffprobe`-verified
between stages so a killed render resumes from the last good chunk instead of
restarting. Peak RSS measured 383–623 MB regardless of final video length.
Full story: [`CASE_STUDIES.md` #1](CASE_STUDIES.md#1-memory-safe-long-form-rendering),
[`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md).

**Trade-off I'd defend:** more process-spawn overhead and more disk I/O for
intermediates, in exchange for a hard memory ceiling and resumability. A
slower resumable render beats a fast one that OOMs.

## "Why RQ instead of Celery?"

One queue, one worker, no complex task graph, no periodic-task framework
need beyond two `time.sleep` loops. Celery's configuration surface (broker
options, result backends, Beat) is real overhead for a workload this simple.
RQ's small surface area also meant the worker-heartbeat bug (below) was
root-causable by reading the actual library source in 20 minutes, not by
tracing a much larger framework. See [ADR-003](docs/adr/003-why-rq.md).

## "Why one worker instead of scaling out?"

Because the failure mode to avoid isn't "renders take longer," it's "two
memory-hungry renders overlap and OOM the box." One shared queue and one
worker makes concurrent rendering structurally impossible — stronger than
coordinating two workers with a lock. Throughput is capped, but Shorts are
paced ~48 minutes apart and there's one long-form video/day, comfortably
inside that ceiling — verified against real timing, not assumed. See
[ADR-002](docs/adr/002-why-redis-queue.md).

## "Tell me about a real production incident."

The one I'd lead with: the Operations dashboard reported the RQ worker as
**Offline** during completely normal idle gaps, while it was in fact
continuously publishing videos on schedule. Instead of just bumping the
threshold, I read the installed `rq==2.10.0` source directly: the library's
blocking dequeue only re-heartbeats when it returns — at most every
`worker_ttl - 15` seconds (~405s for the default 420s TTL) — and
`Worker.all()` already excludes anything whose registration key (TTL
`worker_ttl + 60`) has expired. The app's own check used a **120-second**
threshold — a third of the library's own liveness window. A perfectly
healthy worker idling between jobs 48 minutes apart could have a multi-minute
heartbeat and still be fine; the check just didn't know that.

Fix: stop re-deriving liveness from an invented threshold, trust
`Worker.all()`. Deployed as a single-file, no-migration change. Verified with
a **deliberate 130-second wait** past the old broken threshold before
declaring success — checking immediately after restart would have proven
nothing about the actual regression. Full incident:
[`CASE_STUDIES.md` #2](CASE_STUDIES.md#2-the-worker-was-never-offline).

## "What's the worst bug you shipped, and how did you find it?"

Two candidates, both found by the same discipline (don't trust "this was
already fixed" — re-verify from scratch):

1. A scheduler safety guard ("never start a second job while one is
   `running`") had no expiry. A render killed by unrelated resource
   contention left a project stuck `running` forever, and the guard did
   exactly what it was designed to do — silently refused all further Shorts
   generation on that channel for ~25 hours, no exception thrown anywhere.
   Fixed with a stale-job timeout (30 min) inside the same guard. See
   [`CASE_STUDIES.md` #4](CASE_STUDIES.md#4-the-scheduler-that-stopped-without-saying-anything).
2. `_director_soft_normalize` — a fallback function whose entire job is to
   catch a malformed AI response — referenced an undefined `language`
   variable. It would `NameError` on **every single call**, unconditionally.
   No test caught it because the mocked test provider always returns valid
   JSON, so the fallback path never actually executed in CI. Found by
   running a linter (`ruff`) for the first time on this codebase and
   actually reading what it flagged instead of only auto-fixing the
   mechanical stuff.

## "How do you know the codebase doesn't have secrets in git history?"

Because I found some and had to fix it. A pre-publication `gitleaks` scan
(not manual grep, which had already missed it) found a real OpenAI key and
Stripe test credentials committed months earlier, still present across three
branches. Response: flagged credential rotation as priority one, took a full
mirror backup, used `git filter-repo` for a *targeted* rewrite (specific
strings redacted, one file removed — not a blanket history wipe), then
**independently re-verified against a fresh clone from GitHub** rather than
trusting the local repo — which is what caught that the first push had
missed 28 tags and an orphaned branch still carrying the old history. Full
writeup, including the fact that this is disclosed rather than scrubbed from
the story: [`SECURITY.md`](SECURITY.md).

The same discipline caught a second, smaller version of the same class of
mistake near the end of this work: `.gitleaksignore` allowlisted the 3 known
test-fixture false positives, but not the two places (`SECURITY.md` and the
ignore file's own comment) that quote the same placeholder string while
*explaining* it — which would have made the gitleaks CI job fail on every
push. Found by re-running the scan fresh instead of assuming a past pass was
still valid.

## "Why is deployment manual instead of a CI/CD pipeline?"

The production directory predates this engagement and isn't a git checkout —
converting it mid-project, on a single always-on VPS running a live
publishing schedule, with no staging environment to validate a new pipeline
against, was judged higher risk than the manual procedure it would replace.
The manual procedure isn't sloppy, though: pre-deploy test gate, in-flight-job
check, backup, ship-only-what-changed, migrate, verify, rollback path with a
recorded previous commit. See [`DEPLOYMENT.md`](DEPLOYMENT.md) and
[ADR-001](docs/adr/001-why-docker.md).

**What I'd change on a team:** convert the VPS to a real checkout and add a
tag-triggered CD job that reuses the exact same gates — that's a lower-risk
change than it sounds, because the safety checks already exist; only the
trigger needs automating.

## "What would you refactor first if you inherited this on a team?"

`frontend/app.js` — ~19,000 lines, one file, no build step, no module
boundaries. It works, and there's real discipline inside it (800+ consistent
call sites of an `esc()` XSS-escaping helper), but it's the single biggest
maintainability ceiling in the codebase. I'd split it by route/feature using
native ES modules, still without introducing a bundler — that's why the
Operations dashboard was built as a separate file instead of extending
`app.js`: part of the legacy admin block has character-encoding corruption
from an early migration, and editing near it risked making it worse. See
[`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

## "You kept old SMM/social-posting code around — why not delete it?"

It's real, working code someone still relies on. Deleting functioning
features as a side effect of a repositioning pass is exactly the kind of
unilateral call that should be a deliberate product decision, not incidental
cleanup. The honest cost: the codebase visibly carries two eras of naming at
once (`models.py` next to `saas_models.py`) — documented, not hidden. See
[ADR-006](docs/adr/006-why-youtube-first.md).

## "What did you get wrong that you're not fixing?"

Character-encoding corruption in a few backend files (`saas_api.py`,
`video_niches_config.py`) — not misdecoded bytes (recoverable), but literal
`?` characters where the original text used to be (destroyed, confirmed at
the byte level). I fixed the parts I could reconstruct with full confidence —
a 7-entry weekday-name table, verified correct by matching each corrupted
string's exact character count — and left the longer, unverifiable strings
alone. Fabricating plausible Russian copy to paper over destroyed data would
be a worse outcome than a visible gap. See [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

## "What did this project actually teach you?"

- Read the library's source before arguing with its behavior — the worker
  heartbeat fix only became defensible once I understood RQ's actual
  mechanism, not just widened a number until symptoms went away.
- A verification taken immediately after a fix proves less than it feels
  like it proves, especially for anything time- or state-dependent.
- Automated, scripted checks find real bugs a careful manual pass won't — a
  5px overflow at one exact viewport width, a linter's first-ever run on a
  codebase finding an unconditional `NameError`.
- Finding a security incident in your own repo, in private, before
  publishing, is the process working — not something to quietly clean up
  and never mention.
- "Already checked" is not the same claim as "checked again, right now."
  Two of the most consequential findings in this project's final pass (the
  gitleaksignore gap, `.venv/` never actually being in `.gitignore`) only
  turned up because I re-ran the same checks fresh instead of trusting an
  earlier pass's conclusion.

Full list with more detail: [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md).

## Likely role-specific follow-ups

- **Backend/Python:** "Show me the duplicate-render guard" (`publications_api.py`,
  409 on an existing active/published `Publication`), "walk me through the
  migration system" (`migrations.py`, additive-only, run on boot).
- **AI Engineer:** "How do you keep the AI from repeating itself?" — cooldown/
  reservation on footage assets, anti-repeat topic selection in
  `content_director.py`, a repetition-threshold config surfaced on the
  Content Director UI itself.
- **DevOps:** "Show me the rollback path" (`scripts/rollback.sh`,
  `.prev_release_commit`), "how do you validate prod env vars before deploy"
  (`scripts/validate_production_env.py`, fail-closed, never prints secret
  values).
- **Automation Engineer:** "Why polling loops and not a scheduler framework?"
  — see the ADR-005 answer above; be ready to explain the row-locked
  reservation (`SELECT ... FOR UPDATE SKIP LOCKED`) that makes two scheduler
  ticks unable to double-book a channel's daily slot.
