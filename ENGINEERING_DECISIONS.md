# Engineering Decisions

Key decisions, the reasoning behind them, and — where relevant — what I'd do
differently with more time or on a team codebase. Being asked to defend these
in an interview is the point of writing them down.

## Vanilla JS SPA, no build step

**Decision.** `frontend/app.js` is a single file, no bundler, no framework.

**Why.** The project started as a fast-moving solo effort where a build step
adds friction (a rebuild-and-refresh loop) without buying much for a UI that
doesn't need component reuse across a team.

**What I'd defend, and what I wouldn't.** The "no build step, fast iteration"
call was right for a solo project at this stage. Letting the file grow to
~19,000 lines without ever introducing module boundaries was not something I'd
repeat — it's the single biggest maintainability ceiling in this codebase, and
the fix (splitting by route/feature, even without a bundler, using native ES
modules) is straightforward and overdue. It's also directly why the Operations
dashboard exists as a separate file rather than a new function inside
`app.js` — see below.

## Building Operations as a separate module instead of extending app.js

**Decision.** `frontend/operations.js` is a standalone script, not a new page
function inside `app.js`.

**Why.** Part of `app.js` — the legacy admin panel block — has
character-encoding corruption (Cyrillic text stored as mis-decoded byte
sequences) from an early migration, predating this engagement. The corrupted
region is large and fragile enough that editing near it risks either
introducing further corruption or a subtle double-encoding bug that's hard to
detect by inspection.

**Decision made instead of the two obvious ones.** Global re-encoding the
whole file was rejected — too high blast-radius for a live production frontend,
and the fix would be unverifiable without exhaustively testing every code path
in a 19k-line file. Leaving the feature out was rejected too — the ops
visibility genuinely mattered. The actual fix: build the new feature in a
separate, cleanly-encoded file, wired in with three minimal, surgical edits to
the untouched-otherwise `app.js` (a nav-link entry, a route entry, a mount
point).

**Trade-off, stated plainly.** This works around the underlying encoding bug
rather than fixing it. The honest right answer is a dedicated encoding-repair
pass on that block, done separately, deliberately, and tested in isolation —
not bundled into an unrelated feature's risk budget. That's a known, explicit
remaining item, not an oversight.

**Update: the corruption is broader than this one frontend block.** A later
code-quality pass found the same class of problem in backend Python source
(`api.py`, `dashboard_metrics.py`, `video_niches_config.py`) — but a
worse variant. The frontend case is mis-decoded bytes: recoverable in
principle, given the right codec. The backend case is literal `?` characters
replacing the original text (confirmed at the byte level, not a rendering
artifact) — the original characters are actually gone, not just
misinterpreted. Where the exact original text was unambiguous and safe to
infer (e.g. the seven weekday names in a `dashboard_metrics.py` lookup table,
confirmed correct by matching each corrupted string's exact character count),
it was restored. Longer corrupted strings — user-facing insight sentences,
niche keyword lists — were deliberately left alone rather than guessed at:
fabricating plausible-sounding Russian copy to replace destroyed data would
be worse than leaving the gap visible. This is the same trade-off as the
frontend block, for the same reason, and belongs on the same remaining-work
item rather than as a new one.

## Bearer-token auth in a header, not a session cookie

**Decision.** Auth token in `localStorage`, sent as `Authorization: Bearer
<token>`.

**Why.** This removes CSRF as a threat model entirely for this API — a browser
doesn't auto-attach an `Authorization` header cross-origin the way it does a
cookie, so there's no ambient-credential attack surface to defend against.

**Trade-off, stated plainly.** It raises the stakes of any XSS: a successful
script injection can read the token straight out of `localStorage`. That's why
the escaping discipline (a single `esc()` helper, ~800 call sites, verified
against real user-generated content) isn't optional — it's the actual mitigation
for the risk this auth choice accepts. An `httpOnly` cookie + CSRF-token pair
would remove that specific risk at the cost of reintroducing CSRF handling; I'd
weigh this differently on a system handling higher-value user data than a
single-operator video pipeline.

## One RQ worker, one shared render queue for Shorts and long-form

**Decision.** Both pipelines enqueue onto the same `render` queue, consumed by
a single worker process.

**Why.** On a 3.8 GB box, the failure mode to avoid isn't "renders take a
while" — it's "two memory-hungry renders overlap and OOM the box." A shared
queue with one consumer makes concurrent rendering structurally impossible,
which is a stronger guarantee than trying to coordinate two separate workers
with a lock.

**Trade-off.** Throughput is capped by one worker; a long-form render (several
minutes) can delay the next scheduled Short by that long. Accepted explicitly —
Shorts are paced ~48 minutes apart, so a several-minute delay is absorbed
without missing a slot, and this was verified directly rather than assumed.

## Manual, SSH-driven deployment instead of GitOps

**Decision.** No CI/CD deploy pipeline; deploys are a disciplined manual
procedure (see [`DEPLOYMENT.md`](DEPLOYMENT.md)).

**Why.** The production source directory predates this engagement and isn't a
git checkout; converting it mid-project, on a single VPS actively running a
live automated publishing schedule, was judged higher-risk than the manual
procedure it would replace — especially without a staging environment to
validate the new pipeline against first.

**What I'd defend, and what I wouldn't.** The caution is right for a live
single-operator system with no staging environment. I would not defend leaving
this manual indefinitely on a team project — the natural next step (make the
VPS directory a real checkout, add a tag-triggered deploy job reusing the exact
same pre-deploy gate and backup discipline already in place) is explicitly
scoped in `DEPLOYMENT.md`, not a vague someday.

## Keeping legacy code paths instead of deleting them outright

**Decision.** Social-media-posting code (Facebook publishing, Stripe
billing/plans) from an earlier product scope still exists, reachable from a
secondary UI section, rather than being deleted when the product's primary
positioning moved to YouTube video production.

**Why.** It's real, working, still-used code. Deleting functioning code that
someone still relies on, as a side effect of a repositioning/cleanup pass, is
exactly the kind of unilateral call that should be a deliberate decision by
whoever owns the product — not something to do quietly while tidying up
something else.

**Trade-off.** The codebase carries two eras' worth of naming and structure at
once (e.g. `models.py` alongside `app_models.py`) — a real, visible signal of
incomplete migration. Documented as a known state rather than hidden, because
a reviewer will find it either way.
