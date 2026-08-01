# Lessons Learned

Not a list of features shipped — what this project actually taught, the kind of
thing worth saying out loud in an interview instead of just implying it.

**Read the library's source before arguing with its behavior.** The worker
health-check bug looked, at first glance, like it just needed a bigger
threshold — a guess-and-check fix would probably have "worked" by accident.
Reading the actual `rq` source instead turned a guess into a fix I could
explain and defend: the library's own liveness window is `worker_ttl + 60`,
refreshed at most every `worker_ttl - 15` seconds, and the app's check should
never be stricter than the system it's checking. That's the difference between
patching a symptom and understanding a mechanism.

**A verification that runs immediately after a restart proves less than it
feels like it proves.** The most convincing check for the heartbeat fix wasn't
the one taken right after the backend restarted — it was the one taken after a
deliberate 130-second wait, specifically because the bug was time-dependent and
an early check could pass by coincidence rather than by correctness. Whenever a
fix targets something time- or state-dependent, the honest test is the one
that can't pass by accident.

**"No errors in the last 20 minutes of logs" is not the same claim as "no
regressions."** A deploy verification pass I did initially checked a short log
window and called it clean — which was true, but incomplete: the same
dashboard API I'd already queried was reporting a nonzero `jobs_failed` count
I hadn't reconciled against the log check. Re-verifying against my own claim,
independently, is what caught it. The lesson isn't "check more things" — it's
that a report is only as strong as what you tried to falsify, not what you
happened to look at.

**Automated, scripted checks find things a careful manual pass won't.** A 5-pixel
horizontal overflow at exactly one viewport width, and a false "Offline" status
that only shows up in a narrow multi-minute timing window, are both the kind of
bug that's nearly invisible by eye and mechanically obvious to a script. The
responsive sweep and the deliberate-wait health check both exist because of
this — not as boilerplate test hygiene, but because the specific bugs they
catch don't show up any other way.

**Finding a real security incident on your own repo, in private, before
publishing, is not an embarrassment to hide — it's the process working.** A
`gitleaks` scan that a manual grep had already missed found real credentials in
git history. The instinct to quietly clean it up and never mention it would
have been the wrong one; disclosing exactly what was found and how it was fixed
is more convincing than a repo that simply never mentions the topic.

**Dead code left in a repository is a claim about the author's attention to
detail, whether or not it's true.** A duplicate module tree, six unused
frontend files with no build tooling to explain their presence, and a file
literally named after a typo (`Python/import requests`) didn't break anything
functionally — but every one of them is a small, free piece of negative
evidence for anyone reviewing the repository, and every one of them was cheap
to remove once actually looked for.
