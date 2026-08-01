# Security

## Reporting a vulnerability

Please don't open a public issue for a suspected vulnerability. Use GitHub's
private reporting: this repo's **Security** tab → **Report a vulnerability**
(GitHub Security Advisories). This is a single-maintainer portfolio project,
not a production service handling third-party user data, but a real report
will still get read and acknowledged.

## A real incident, found and fixed before this repository was ever public

A pre-publication audit ran `gitleaks` (not just manual grep) across the full
git history and found 8 matches. Three were a false positive (a test file
setting `STRIPE_SECRET_KEY` to the literal string `"sk_test_configured"` via
`monkeypatch`, to satisfy a truthiness check — not a real key; now allow-listed
in `.gitleaksignore` with the reasoning documented inline). The other five were
real:

- A real OpenAI project API key, committed in a plaintext file in February.
- A real Stripe test-mode secret key and webhook signing secret, committed in
  `.env.example` (and a duplicate copy under `deploy/release/`) the same month.

**What was verified before deciding how to respond:**
- The current `HEAD` of every file was already clean (someone had already
  blanked the values in a later commit) — but the real values were still
  reachable in history via `git log`/`git show`.
- The repository's visibility was checked directly (`gh repo view`): **private**
  at the time, not yet exposed to the public internet.
- The affected commits were confirmed present on `origin` — `main` and two
  feature branches — meaning the secrets were on GitHub's servers, not just
  local.
- A previously-unknown branch (`portfolio/readme-refresh`) and 28 internal
  QA-automation tags were also found to reference the same pre-cleanup history
  — a plain "fix the 3 known branches" approach would have missed them.

**Remediation, in order:**
1. Credential rotation flagged as the first, non-negotiable action — rewriting
   history does not undo an already-committed secret; only rotating the actual
   credential does.
2. A full mirror clone taken as a rollback point before any history rewrite.
3. `git filter-repo` used to (a) surgically replace the exact leaked secret
   strings with a redaction marker across every commit, and (b) remove the
   plaintext-key file from history entirely — not a blanket "wipe everything"
   rewrite, a targeted one.
4. Verified locally with a fresh `gitleaks` scan post-rewrite (0 real matches)
   before touching the remote.
5. Force-pushed the rewritten history to all three affected branches, deleted
   the stale unreferenced branch, and force-pushed the rewritten tags.
6. **Independently re-verified against a brand-new clone from GitHub** (not the
   local working copy) — this caught that tags hadn't been included in the
   first push pass, since a fresh mirror clone scan found 11 leaks where the
   local repo showed 3. Re-ran the tag push, re-cloned again: 0 real leaks.
7. All local files that had held the plaintext secrets during this process
   (scan reports, the replacement-rules file, the pre-rewrite backup clone)
   were deleted once the fix was confirmed.
8. Added `gitleaks` as a CI job (`.github/workflows/tests.yml`) so this class of
   mistake gets caught automatically going forward, not just in a one-off
   manual pass.

This is disclosed here deliberately rather than quietly cleaned up and
forgotten — a reviewer who runs their own `gitleaks` scan against this repo
should find nothing, and should be able to see that the absence of findings is
the result of a real process, not luck.

## Application-level review (what was actually checked)

| Class | Finding |
|---|---|
| Command injection | No `shell=True`, `os.system`, or `os.popen` anywhere in the codebase. Every `subprocess` call (FFmpeg included) uses list-form arguments, which is not shell-interpretable. |
| SQL injection | All application queries go through the SQLAlchemy ORM (parameterized). The only raw `text()` SQL with string interpolation is in `migrations.py`, building `ALTER TABLE`/`ADD COLUMN` statements from hardcoded developer-defined column dictionaries in the same file — never from request data, so it isn't an injectable path despite the interpolation. |
| XSS | Frontend rendering goes through a single `esc()` helper, used at 800+ call sites including every point where user- or AI-generated text (post titles, project names) is inserted into `innerHTML`. Spot-checked directly in the calendar-post render path. |
| CSRF | Authentication is a `Authorization: Bearer <token>` header read from `localStorage`, not an ambient cookie — the browser doesn't auto-attach it cross-origin, which removes the CSRF threat model entirely for this API surface (the trade-off is that XSS becomes higher-stakes, which is why the escaping discipline above matters). |
| CORS | Explicit origin allowlist from `CORS_ORIGIN`/`FRONTEND_BASE_URL`, `supports_credentials=True` paired with a specific origin list, not a wildcard. |
| Secrets in current code | `.env` is git-ignored and was confirmed never tracked; no hardcoded credentials found in the current tree by either manual grep or `gitleaks`. |

## What this review did not attempt

- No dependency-vulnerability scan tool was run against `requirements.txt`
  (e.g. `pip-audit`) as part of this pass — a reasonable next step, not done
  here because it wasn't available in this environment at the time.
- No formal penetration test — this is a source-level review, not a black-box
  security assessment.
- No infrastructure-level review of the VPS itself (SSH hardening, firewall
  rules) beyond what's directly relevant to the application.
