# Video Planner Release - queue-safe planner and live verified deploy

Release date: 2026-04-12

Deployed commit: aebbe4a
Production target: /opt/autosocial
Active source path: /opt/autosocial/src

## What Shipped

- Unified /create/video planner experience aligned with Post Studio product UI.
- Queue-safe 1-day, 7-day, and 30-day draft planning.
- Draft-only plan generation so long plans do not trigger unsafe bulk rendering.
- Queue metadata for selected render jobs, including status, stage, and ETA visibility.
- Backend and worker release deployed with capacity-aware queue behavior.
- Footage-based video rendering preserved; no OpenAI image generation path introduced.
- Single render path verified locally before deploy.

## Live Verification

- /create/video loads: PASS
- 1-day plan generation: PASS
- Queue one item: PASS
- Queue metadata visible: PASS
- Stage visible: PASS
- Fatal console/app/API errors: none observed

## Rollback Reference

- Deployed release commit: aebbe4a
- Production backup created during deploy: /opt/autosocial/release_backup_aebbe4a_20260412_212615
- Rollback source: restore the backed-up files from that directory into /opt/autosocial/src, then restart backend and worker services.

## Final Verdict

Video planner release is live-smoke verified and safe to keep live.
