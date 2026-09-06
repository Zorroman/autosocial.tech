#!/usr/bin/env bash
# Hardened, fail-closed PRODUCTION deploy. Runs ON THE SERVER, MANUALLY.
# Never triggered automatically. Supports DEPLOY_DRY_RUN=1 for a fully local,
# network-free rehearsal (temp dirs, no restart, no real services).
#
# Sequence (each step aborts the deploy on failure):
#   1 acquire deployment lock (flock)      9 frontend integrity BEFORE activation
#   2 record current commit               10 migrations (backup-gated)
#   3 disk-space check                    11 atomic activate release + frontend
#   4 backup database (validated)         12 verify FINAL frontend SHA
#   5 backup current frontend/app.js      13 restart services
#   6 stage release in temp location      14 health check
#   7 install dependencies                15 API/browser smoke
#   8 validate production environment     16 release lock (trap)
#
# On failure AFTER activation: restore previous code + previous app.js + restart.
# The database backup is NOT auto-restored (migrations are additive; restoring a
# DB after a partially-applied migration is unsafe and must be a human decision).
#
# Required env:
#   TARGET_COMMIT           release commit to deploy
#   FRONTEND_EXPECTED_SHA   sha256 of the release's frontend/app.js
# Optional env:
#   APP_DIR RELEASE_SOURCE BACKUP_DIR LOCK_FILE API_URL FRONT_URL
#   COMPOSE_DIR RESTART_MODE WEB_SERVICE WORKER_SERVICE MIN_FREE_MB DEPLOY_DRY_RUN
#   CONFIRM_REPLACE_APP_SOURCE
set -euo pipefail
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8   # guard against mojibake on copy

DRY_RUN="${DEPLOY_DRY_RUN:-0}"
# Target paths/hosts are injected by the operator's private deploy environment.
# No production path or hostname is baked into this file; unset -> fail closed.
APP_DIR="${APP_DIR:-}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
LOCK_FILE="${LOCK_FILE:-${BACKUP_DIR}/deploy.lock}"
MIN_FREE_MB="${MIN_FREE_MB:-500}"
API_URL="${API_URL:-}"
FRONT_URL="${FRONT_URL:-}"
RESTART_MODE="${RESTART_MODE:-passenger}"
WEB_SERVICE="${WEB_SERVICE:-autosocial-web}"
WORKER_SERVICE="${WORKER_SERVICE:-autosocial-worker}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_RSYNC_EXCLUDES=(
  --exclude='.git/'
  --exclude='.env'
  --exclude='.env.*'
  --exclude='data/'
  --exclude='output/'
  --exclude='cache/'
  --exclude='generated_media/'
  --exclude='logs/'
  --exclude='tmp/'
  --exclude='*.db'
  --exclude='__pycache__/'
)

STAMP="$(date +%Y%m%d_%H%M%S)"
ACTIVATED=0
PREV_APP_JS_BACKUP=""
PREV_SOURCE_BACKUP=""

log()  { echo "[deploy $STAMP] $*"; }
fail() { echo "DEPLOY FAILED: $1" >&2; post_failure_rollback "$1"; exit 1; }

verify_release_source_revision() {
  local source_dir="$1"
  local actual=""
  if [ -e "$source_dir/.git" ]; then
    actual="$(cd "$source_dir" && git rev-parse HEAD)" || return 1
  elif [ -f "$source_dir/.deployed_commit" ]; then
    actual="$(cat "$source_dir/.deployed_commit")"
  elif [ -f "$source_dir/.release_commit" ]; then
    actual="$(cat "$source_dir/.release_commit")"
  else
    echo "release source has no .git, .deployed_commit, or .release_commit provenance marker" >&2
    return 1
  fi
  if [ "$actual" != "$TARGET_COMMIT" ]; then
    echo "release source revision mismatch: expected $TARGET_COMMIT, got $actual" >&2
    return 1
  fi
}

post_failure_rollback() {
  if [ "$ACTIVATED" = "1" ]; then
    log "ROLLBACK: restoring previous code + frontend"
    if [ -n "$PREV_SOURCE_BACKUP" ] && [ -d "$PREV_SOURCE_BACKUP" ]; then
      # Do not use --delete here. The source backup intentionally excludes
      # runtime-owned paths (.env, data, logs, cache, generated output); a
      # deleting rollback could remove those production-only paths.
      rsync -a "${APP_RSYNC_EXCLUDES[@]}" "$PREV_SOURCE_BACKUP"/ "$APP_DIR"/ || true
    fi
    if [ -n "$PREV_APP_JS_BACKUP" ] && [ -f "$PREV_APP_JS_BACKUP" ]; then
      cp "$PREV_APP_JS_BACKUP" "$APP_DIR/frontend/app.js" || true
    fi
    if [ "$DRY_RUN" != "1" ]; then
      if [ -f "$APP_DIR/.prev_release_commit" ]; then
        export GIT_SHA
        GIT_SHA="$(cat "$APP_DIR/.prev_release_commit")"
      fi
      if [ -n "${COMPOSE_DIR:-}" ] && [ -f "$COMPOSE_DIR/docker-compose.yml" ]; then
        ( cd "$COMPOSE_DIR" && docker compose build --build-arg "GIT_SHA=${GIT_SHA:-unknown}" backend worker ) || true
        ( cd "$COMPOSE_DIR" && docker compose up -d backend worker ) || true
      else
        restart_services || true
      fi
    fi
    log "ROLLBACK done. DB backup left intact (manual restore only if needed): $BACKUP_DIR"
  else
    log "failure before activation — nothing was changed on the live release"
  fi
}

restart_services() {
  [ "$DRY_RUN" = "1" ] && { log "(dry-run) skip restart"; return 0; }
  if [ "$RESTART_MODE" = "systemd" ]; then
    sudo systemctl restart "$WEB_SERVICE"
    sudo systemctl restart "$WORKER_SERVICE"
  else
    mkdir -p "$APP_DIR/tmp" && touch "$APP_DIR/tmp/restart.txt"
    pkill -f "python3? worker.py" || true
    ( cd "$APP_DIR" && nohup python3 worker.py >> logs/worker.log 2>&1 & )
  fi
}

: "${TARGET_COMMIT:?set TARGET_COMMIT}"
: "${FRONTEND_EXPECTED_SHA:?set FRONTEND_EXPECTED_SHA (sha256 of release frontend/app.js)}"
: "${APP_DIR:?set APP_DIR (live release directory; no default is baked in)}"
COMPOSE_DIR="${COMPOSE_DIR:-$(dirname "$APP_DIR")}"
# Live health/smoke targets are only needed for a real (non-dry-run) deploy.
if [ "$DRY_RUN" != "1" ]; then
  : "${API_URL:?set API_URL (health/smoke target)}"
  : "${FRONT_URL:?set FRONT_URL (smoke target)}"
fi
mkdir -p "$BACKUP_DIR"

# ---- 1. deployment lock (flock on Linux, atomic mkdir fallback) ------------
# Both mechanisms are atomic: a second concurrent deploy fails immediately.
# Stale locks older than LOCK_STALE_SECONDS are reclaimed safely.
LOCK_DIR="${LOCK_FILE}.d"
LOCK_STALE_SECONDS="${LOCK_STALE_SECONDS:-3600}"
LOCK_MODE=""
release_lock() {
  [ "$LOCK_MODE" = "flock" ] && { flock -u 9 2>/dev/null || true; }
  rm -rf "$LOCK_DIR" 2>/dev/null || true
  rm -f "$LOCK_FILE" 2>/dev/null || true
}
if command -v flock >/dev/null 2>&1; then
  LOCK_MODE="flock"
  exec 9>"$LOCK_FILE" || fail "cannot open lock file $LOCK_FILE"
  if ! flock -n 9; then
    echo "DEPLOY ABORTED: another deployment holds the lock ($LOCK_FILE)"; exit 3
  fi
  echo "pid=$$ ts=$STAMP commit=$TARGET_COMMIT" >&9 || true
else
  LOCK_MODE="mkdir"
  # reclaim a stale lock
  if [ -d "$LOCK_DIR" ]; then
    lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || stat -c %Y "$LOCK_DIR" 2>/dev/null || echo 0) ))
    [ "$lock_age" -gt "$LOCK_STALE_SECONDS" ] && rm -rf "$LOCK_DIR"
  fi
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "DEPLOY ABORTED: another deployment holds the lock ($LOCK_DIR)"; exit 3
  fi
  echo "pid=$$ ts=$STAMP commit=$TARGET_COMMIT" > "$LOCK_DIR/owner" || true
fi
trap 'release_lock' EXIT
log "lock acquired ($LOCK_MODE: $LOCK_FILE)"

# ---- 2. record current deployed revision ------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  if [ -d "$APP_DIR/.git" ]; then
    ( cd "$APP_DIR" && git rev-parse HEAD ) > "$APP_DIR/.prev_release_commit" || fail "record current commit"
  elif [ -f "$APP_DIR/.deployed_commit" ]; then
    cp "$APP_DIR/.deployed_commit" "$APP_DIR/.prev_release_commit" || fail "record current deployed commit"
  else
    echo "unknown" > "$APP_DIR/.prev_release_commit" || fail "record unknown deployed commit"
  fi
  log "previous commit: $(cat "$APP_DIR/.prev_release_commit")"
else
  log "(dry-run) skip real commit record"
fi

# ---- 3. disk-space check ----------------------------------------------------
FREE_MB=$(df -Pm "$BACKUP_DIR" | awk 'NR==2{print $4}')
[ "${FREE_MB:-0}" -ge "$MIN_FREE_MB" ] || fail "insufficient free space: ${FREE_MB}MB < ${MIN_FREE_MB}MB"
log "free space OK: ${FREE_MB}MB"

# ---- 4. backup database (validated: must exist and be non-empty) ------------
DB_BACKUP=""
if [ -f "$APP_DIR/autosocial.db" ]; then
  DB_BACKUP="$BACKUP_DIR/db_$STAMP.db"
  sqlite3 "$APP_DIR/autosocial.db" ".backup '$DB_BACKUP'" || fail "sqlite backup"
elif [ -n "${DATABASE_URL:-}" ]; then
  DB_BACKUP="$BACKUP_DIR/db_$STAMP.sql"
  pg_dump "$DATABASE_URL" > "$DB_BACKUP" || fail "pg_dump"
fi
if [ -n "$DB_BACKUP" ]; then
  [ -s "$DB_BACKUP" ] || fail "database backup is empty: $DB_BACKUP"
  log "db backup validated: $DB_BACKUP ($(wc -c < "$DB_BACKUP") bytes)"
else
  log "no database configured to back up"
fi

# ---- 5. backup current frontend/app.js -------------------------------------
PREV_SOURCE_BACKUP="$BACKUP_DIR/source_$STAMP"
mkdir -p "$PREV_SOURCE_BACKUP"
rsync -a \
  "${APP_RSYNC_EXCLUDES[@]}" \
  "$APP_DIR"/ "$PREV_SOURCE_BACKUP"/ || fail "backup current source"
log "source backup validated: $PREV_SOURCE_BACKUP"

if [ -f "$APP_DIR/frontend/app.js" ]; then
  PREV_APP_JS_BACKUP="$BACKUP_DIR/app.js_$STAMP.bak"
  cp "$APP_DIR/frontend/app.js" "$PREV_APP_JS_BACKUP" || fail "backup app.js"
  log "app.js backed up: $PREV_APP_JS_BACKUP"
fi

# ---- 6. stage the release in a temporary location --------------------------
# RELEASE_SOURCE is a directory containing the new release tree (incl.
# frontend/app.js). In real use it is produced by checkout/rsync of TARGET_COMMIT.
[ -n "${RELEASE_SOURCE:-}" ] || fail "RELEASE_SOURCE not set (staged release dir)"
[ -d "$RELEASE_SOURCE" ] || fail "RELEASE_SOURCE missing: $RELEASE_SOURCE"
STAGED_JS="$RELEASE_SOURCE/frontend/app.js"
[ -f "$STAGED_JS" ] || fail "staged frontend/app.js missing in RELEASE_SOURCE"
verify_release_source_revision "$RELEASE_SOURCE" || fail "RELEASE_SOURCE does not prove TARGET_COMMIT"
log "release staged at $RELEASE_SOURCE"

# ---- 7. install dependencies -----------------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  ( cd "$RELEASE_SOURCE" && pip install -r requirements.txt --quiet ) || fail "pip install"
else
  log "(dry-run) skip pip install"
fi

# ---- 8. validate production environment ------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  python3 "$SCRIPT_DIR/validate_production_env.py" --require production --quiet || fail "production env validation"
else
  log "(dry-run) skip env validation"
fi

# ---- 9. frontend integrity of the STAGED file BEFORE activation ------------
bash "$SCRIPT_DIR/verify_deployed_frontend.sh" "$FRONTEND_EXPECTED_SHA" "$STAGED_JS" \
  || fail "staged frontend integrity/SHA check failed — NOT activating"
log "staged frontend verified before activation"

# ---- 10. migrations (only after a validated backup exists) -----------------
if [ "$DRY_RUN" != "1" ]; then
  [ -z "$DB_BACKUP" ] || [ -s "$DB_BACKUP" ] || fail "refusing migrations without a valid backup"
  ( cd "$RELEASE_SOURCE" && python3 migrations.py ) || fail "migrations failed — release NOT activated"
else
  # dry-run: exercise migrations against a throwaway sqlite copy of the backup
  if [ -n "$DB_BACKUP" ] && [ -s "$DB_BACKUP" ]; then
    TMPDB="$BACKUP_DIR/dryrun_migrate_$STAMP.db"; cp "$DB_BACKUP" "$TMPDB"
    ( cd "$RELEASE_SOURCE" && DATABASE_URL="sqlite:///$TMPDB" python3 migrations.py ) \
      || fail "(dry-run) migrations failed on backup copy — release NOT activated"
    rm -f "$TMPDB"
  fi
fi
log "migrations OK"

# ---- 11. activation of release source + frontend ---------------------------
# APP_DIR may be either a git checkout or an artifact copy. In both cases the
# release source must come from TARGET_COMMIT, and .deployed_commit is the
# runtime traceability marker verified after deployment.
ACTIVATED=1
if [ "$DRY_RUN" != "1" ] && [ -d "$APP_DIR/.git" ]; then
  ( cd "$APP_DIR" && git checkout "$TARGET_COMMIT" ) || fail "checkout $TARGET_COMMIT"
else
  if [ "$DRY_RUN" != "1" ] && [ "${CONFIRM_REPLACE_APP_SOURCE:-}" != "1" ]; then
    fail "refusing --delete artifact activation without CONFIRM_REPLACE_APP_SOURCE=1"
  fi
  mkdir -p "$APP_DIR"
  rsync -a --delete \
    "${APP_RSYNC_EXCLUDES[@]}" \
    "$RELEASE_SOURCE"/ "$APP_DIR"/ || fail "sync release artifact into APP_DIR"
fi
printf '%s\n' "$TARGET_COMMIT" > "$APP_DIR/.deployed_commit" || fail "write deployed revision marker"
NEW_JS="$APP_DIR/frontend/.app.js.new.$STAMP"
mkdir -p "$APP_DIR/frontend"
cp "$STAGED_JS" "$NEW_JS" || fail "copy staged app.js"
mv -f "$NEW_JS" "$APP_DIR/frontend/app.js" || fail "atomic rename app.js"
if [ "$DRY_RUN" != "1" ]; then
  export GIT_SHA="$TARGET_COMMIT"
  ( cd "$COMPOSE_DIR" && docker compose build --build-arg "GIT_SHA=$TARGET_COMMIT" backend worker ) \
    || fail "docker build with revision label"
  ( cd "$COMPOSE_DIR" && docker compose up -d backend worker ) || fail "restart backend/worker containers"
fi
log "release activated"

# ---- 12. verify FINAL frontend SHA -----------------------------------------
bash "$SCRIPT_DIR/verify_deployed_frontend.sh" "$FRONTEND_EXPECTED_SHA" "$APP_DIR/frontend/app.js" \
  || fail "post-activation frontend SHA mismatch"
log "final frontend verified"

# ---- 13. restart services ---------------------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  log "backend/worker already recreated by docker compose"
else
  restart_services || fail "service restart"
fi

# ---- 14. health -------------------------------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  sleep 8
  curl -fsS --max-time 15 "$API_URL/api/health" >/dev/null || fail "health check"
else
  log "(dry-run) skip health check"
fi

# ---- 15. smoke --------------------------------------------------------------
if [ "$DRY_RUN" != "1" ]; then
  python3 "$SCRIPT_DIR/post_deploy_smoke.py" --api "$API_URL" --front "$FRONT_URL" || fail "post-deploy smoke"
else
  log "(dry-run) skip smoke"
fi

# ---- 16. lock released by trap ---------------------------------------------
log "DEPLOY SUCCEEDED (commit $TARGET_COMMIT)${DRY_RUN:+ [dry-run=$DRY_RUN]}"
