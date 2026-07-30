# Case Studies

Real incidents from this project, in the order they matter most for a technical
conversation. Each follows: Problem → Investigation → Root Cause → Decision →
Implementation → Trade-offs → Result. Nothing here is hypothetical.

## 1. Memory-safe long-form rendering

**Problem.** An 11-minute 1080p render OOM-killed the worker process at ~40%
progress, every time, on a 3.8 GB VPS with no swap.

**Investigation.** The existing renderer built one FFmpeg `filter_complex` graph
across every clip in the timeline and encoded the whole thing in a single
process. That process's memory footprint scales with the number of decoded
inputs held simultaneously — for a 15–20 segment long-form video, that's every
segment's decoded frames alive at once.

**Root cause.** Not a tuning problem — a monolithic filter graph is
fundamentally the wrong shape for this hardware, regardless of encoder
settings. It would eventually OOM on any sufficiently long video.

**Decision.** Redesign the renderer so peak memory is bounded by *one segment*,
not by video length — explicitly rejecting the two easy-but-wrong fixes: buying
a bigger VPS (outside the given constraint) and downgrading to 720p (a real
quality regression, rejected outright).

**Implementation.** `longform_render.py`: each still/clip becomes its own short
FFmpeg process producing a small segment file; segments are grouped into
chunks and stream-copied (`-c copy`, no re-encode) with `ffprobe` verification
per chunk; chunks are stream-copied into the final file. Every intermediate
artifact is a real file, so a killed render resumes from the last verified
chunk instead of restarting.

**Trade-offs.** More FFmpeg process invocations (higher process-spawn overhead)
in exchange for a hard memory ceiling; more disk I/O for intermediate files in
exchange for resumability. Both accepted deliberately — a slightly slower,
resumable render beats a fast one that OOMs.

**Result.** Peak RSS 383–623 MB across multiple real production renders (9–14
minutes), independent of video length. Zero OOM kills, zero swap usage since.

## 2. The worker was never offline

**Problem.** The Operations dashboard reported the RQ worker as `Offline`
during completely normal idle gaps — even though it was, in fact, continuously
publishing videos on schedule throughout.

**Investigation.** Rather than assume the threshold was "roughly right,"
verified by *reading the installed `rq==2.10.0` source directly*: the library's
blocking dequeue call only re-heartbeats when it returns, at most every
`worker_ttl - 15` seconds (~405 s for the library's own 420 s default), and
`Worker.all()` already excludes any worker whose registration key has expired
(the library sets that key's TTL to `worker_ttl + 60`, refreshed on heartbeat).

**Root cause.** The application's own health check re-derived "aliveness" from
heartbeat age using a **120-second** threshold — roughly a third of the
library's own liveness window. A perfectly healthy, idle worker (jobs run
~48 minutes apart on this system) could legitimately have a multi-minute-old
heartbeat and still be completely fine; the check just didn't know that.

**Decision.** Stop re-deriving liveness from a shorter, invented threshold.
Trust the queue library's own bookkeeping — presence in `Worker.all()` already
means "not expired by the library's own TTL." Keep a per-worker heartbeat-age
detail for diagnostics, but measure it against *that worker's own configured
`worker_ttl`*, not a constant, so it stays correct if the TTL is ever tuned.

**Implementation.** `factory_dashboard_api.py::_worker_status` — `online` is
now `bool(Worker.all(...))`; the diagnostic `alive` flag per worker uses
`worker_ttl + 60`. Two regression tests added: a worker with a 300-second-old
heartbeat is `online`; a worker with no registration at all is not.

**Trade-offs.** None found — this was a strictly-more-correct fix with no
downside; the old threshold provided no real protection it didn't already get
from the library's own expiry.

**Result.** Deployed as a single-file, no-migration change (worker container
never touched). Verified live: after an explicit 130-second wait, heartbeat age
354 s — nearly 3× the old broken threshold — `/api/readiness` correctly
reported `ready`. Declaring success from the first, immediate post-restart
check would have proven nothing about the actual regression; the deliberate
wait is what makes this verification real.

## 3. Subtitle sync via forced alignment

**Problem.** Long-form subtitles drifted visibly out of sync with the
voiceover on long narration scenes (~40 s each).

**Investigation.** The existing subtitle builder distributed word timing
*proportionally to word length* within each scene's estimated duration — an
approach the code's own comments already flagged as an "honest limitation" for
short clips, but one that compounds badly over long scenes where real speech
pace varies.

**Root cause.** Proportional timing was never actually timing — it was a
length-weighted guess, with no relationship to the real audio.

**Decision.** Replace the guess with ground truth: transcribe the finished
voiceover with Whisper (`whisper-1`, word-level timestamps) and build subtitle
cues from the actual spoken timing. Keep the proportional method only as a
fallback if transcription is ever unavailable.

**Implementation.** `_transcribe_words()` / `_pack_aligned_cues()` /
`write_aligned_ass()` in `longform_pipeline.py`. Verified on a real render:
1364 words with real timestamps (e.g. `Луна 0.00–0.60s ... садоводства
749.22–749.86s`), 118 subtitle cues, word-level "pop" emphasis timed to the
exact word being spoken.

**Trade-offs.** An extra API call (transcription) per long-form video, and a
dependency on that call succeeding — mitigated by the fallback path rather than
making transcription a hard requirement.

**Result.** User-confirmed synced on the resulting render. Became the basis for
a second feature (glossary term callouts timed to real speech) once real
word-level timing existed to build on.

## 4. The scheduler that stopped without saying anything

**Problem.** Automated Shorts generation silently stopped for ~25 hours — no
exceptions, no failed jobs, nothing in the logs indicating a problem.

**Investigation.** The scheduler enforces "at most one actively-running
pipeline per channel" by checking for any `VideoProject` with
`pipeline_state="running"`. A render that had been killed by an unrelated
resource-contention issue left exactly one project stuck in that state
forever — so the scheduler was doing exactly what it was designed to do:
correctly refusing to start a second job while one was (apparently) still
running. It was waiting on a job that would never finish, and had no way to
know that.

**Root cause.** A "one job at a time" safety guard with no expiry — correct
under normal operation, silently fatal under a crash.

**Decision.** Add a stale-job timeout to the guard itself, rather than relying
on manual detection after the fact.

**Implementation.** `scheduler.py::_reserve` — any project `running` longer
than `FACTORY_RUNNING_STALE_MIN` (default 30 minutes, comfortably longer than
any real render takes) is treated as dead, reset to `needs_review`, and no
longer blocks new generation.

**Trade-offs.** A 30-minute window means a genuinely-stuck job still blocks
generation for up to half an hour before self-healing — accepted, since a real
render never legitimately takes that long, and the alternative (a much shorter
window) risks false-triggering on a slow-but-healthy render.

**Result.** The specific outage that surfaced this was resolved manually once
found; the self-heal fix means the same class of failure now recovers on its
own within 30 minutes instead of requiring a human to notice a multi-day gap
in publish activity.

## 5. A security incident found by the tool built to prevent it

Full incident writeup in [`SECURITY.md`](SECURITY.md) — summarized here for
the case-study format: a pre-publication `gitleaks` scan (not manual grep, which
had already missed it) found a real OpenAI key and Stripe test credentials
committed to git history months earlier, still present on the private GitHub
remote across three branches. Response: credential-rotation flagged as
priority one, a full mirror backup taken, `git filter-repo` used for a
*targeted* rewrite (specific secret strings redacted, one leaked file removed
entirely — not a blanket history wipe), verified locally, force-pushed, then
**independently re-verified against a fresh clone from GitHub** — which caught
that the first push pass had missed 28 tags and an orphaned branch still
referencing the old history. Fixed, re-verified clean, and a `gitleaks` CI job
added so this can't silently recur.

## 6. The overflow the manual eyeball pass would have missed

**Problem.** A scripted responsive sweep (10 pages × 4 viewports, asserting
`scrollWidth <= innerWidth` and zero console errors) found real horizontal
overflow on 3 page/viewport combinations — all at exactly 1024×768.

**Investigation.** Direct DOM inspection at the failing viewport showed the
top-level layout `<div>` was 1029 px wide inside a 1024 px viewport — a 5 px
overflow that a casual look wouldn't catch, but that fails the "no horizontal
scroll" bar unambiguously.

**Root cause.** `.layout { grid-template-columns: 260px 1fr; }` — CSS grid
items default to `min-width: auto`, so the content column refused to shrink
below its content's natural width (a wide table, a row of topbar buttons),
pushing the whole grid past the viewport.

**Decision.** Fix the actual grid track, not the individual pages that
happened to have wide-enough content to trigger it — the same bug would
recur on any future page with a wide table or a long button row.

**Implementation.** `grid-template-columns: 260px minmax(0, 1fr);` plus
`min-width: 0` guards on the shell/content containers and `overflow-x: auto`
scoping for wide tables below 900 px.

**Trade-offs.** None — this is a strictly-correct CSS fix with no visual
change on any viewport that wasn't already overflowing.

**Result.** Re-ran the same automated sweep: 0 overflow issues across all
40 combinations, 0 console errors. The bug is now also structurally
harder to reintroduce, since the fix is at the layout-primitive level, not a
per-page patch.
