#!/usr/bin/env bash
# TEST-deployment script. Runs ON THE SERVER, MANUALLY. Never triggered
# automatically. Fail-fast: any error triggers rollback.
#
# Usage (on server):
#   APP_DIR=/var/www/api-dev TARGET_COMMIT=2bcb420... bash scripts/deploy_test.sh
#
# Configure via env (defaults suit the ADM.tools dev layout):
APP_DIR="${APP_DIR:-/var/www/api-dev}"
TARGET_COMMIT="${TARGET_COMMIT:?set TARGET_COMMIT to the release commit hash}"
API_URL="${API_URL:-https://api-dev.autosocial.tech}"
FRONT_URL="${FRONT_URL:-https://dev.autosocial.tech}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
# Restart mode: "passenger" (touch tmp/restart.txt) or "systemd"
RESTART_MODE="${RESTART_MODE:-passenger}"
WEB_SERVICE="${WEB_SERVICE:-autosocial-web}"
WORKER_SERVICE="${WORKER_SERVICE:-autosocial-worker}"

set -euo pipefail
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8   # guard against mojibake on copy
cd "$APP_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

fail() { echo "DEPLOY FAILED: $1"; echo "Run: bash scripts/rollback.sh"; exit 1; }

echo "== 1. backup =="
git rev-parse HEAD > "$BACKUP_DIR/prev_commit_$STAMP" || fail "cannot record current commit"
cp "$BACKUP_DIR/prev_commit_$STAMP" "$APP_DIR/.prev_release_commit"
if [ -f autosocial.db ]; then
  sqlite3 autosocial.db ".backup '$BACKUP_DIR/db_$STAMP.db'" || fail "sqlite backup"
elif [ -n "${DATABASE_URL:-}" ]; then
  pg_dump "$DATABASE_URL" > "$BACKUP_DIR/db_$STAMP.sql" || fail "pg_dump"
fi
echo "backup done: $BACKUP_DIR (commit $(cat .prev_release_commit))"

echo "== 2. fetch target commit =="
git fetch origin || fail "git fetch"
git status --porcelain | grep -q . && fail "working tree dirty on server"
git checkout "$TARGET_COMMIT" || fail "checkout $TARGET_COMMIT"

echo "== 3. dependencies =="
pip install -r requirements.txt --quiet || fail "pip install"

echo "== 4. frontend integrity (no build step; gate = build) =="
bash scripts/check_frontend_integrity.sh || fail "frontend integrity"

echo "== 5. migrations (additive) =="
python3 migrations.py || fail "migrations"

echo "== 6/7. restart web + worker =="
if [ "$RESTART_MODE" = "systemd" ]; then
  sudo systemctl restart "$WEB_SERVICE" || fail "web restart"
  sudo systemctl restart "$WORKER_SERVICE" || fail "worker restart"
else
  mkdir -p tmp && touch tmp/restart.txt   # Passenger web restart
  # Worker under Passenger hosting runs via cron/screen; restart it explicitly:
  pkill -f "python3? worker.py" || true
  nohup python3 worker.py >> logs/worker.log 2>&1 &
fi
sleep 8

echo "== 8. health =="
curl -fsS --max-time 15 "$API_URL/api/health" > /dev/null || fail "health check"

echo "== 9/10. readiness + smoke =="
python3 scripts/post_deploy_smoke.py --api "$API_URL" --front "$FRONT_URL" || fail "smoke"

echo ""
echo "TEST DEPLOYMENT SUCCEEDED: $(git rev-parse --short HEAD)"
