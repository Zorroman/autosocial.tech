#!/usr/bin/env bash
# Rollback to the release recorded by deploy_test.sh (.prev_release_commit).
# Run ON THE SERVER, MANUALLY.
APP_DIR="${APP_DIR:-/var/www/api-dev}"
API_URL="${API_URL:-https://api-dev.autosocial.tech}"
RESTART_MODE="${RESTART_MODE:-passenger}"
WEB_SERVICE="${WEB_SERVICE:-autosocial-web}"
WORKER_SERVICE="${WORKER_SERVICE:-autosocial-worker}"

set -euo pipefail
cd "$APP_DIR"

PREV=$(cat .prev_release_commit 2>/dev/null || true)
[ -n "$PREV" ] || { echo "FAIL: .prev_release_commit not found"; exit 1; }

echo "Rolling back to $PREV"
git checkout "$PREV"
pip install -r requirements.txt --quiet

if [ "$RESTART_MODE" = "systemd" ]; then
  sudo systemctl restart "$WEB_SERVICE"
  sudo systemctl restart "$WORKER_SERVICE"
else
  mkdir -p tmp && touch tmp/restart.txt
  pkill -f "python3? worker.py" || true
  nohup python3 worker.py >> logs/worker.log 2>&1 &
fi
sleep 8

curl -fsS --max-time 15 "$API_URL/api/health" > /dev/null \
  && echo "ROLLBACK OK: health passed on $PREV" \
  || { echo "ROLLBACK COMPLETED BUT HEALTH FAILED — investigate manually"; exit 1; }
echo "Note: migrations are additive; DB restore from backup is only needed on data corruption (see docs/history/BACKUP_RESTORE.md)."
