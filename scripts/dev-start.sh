#!/usr/bin/env bash
# Development-only stack: backend (mock providers, isolated SQLite) + frontend
# with SPA fallback. Never used for production.
#
#   ./scripts/dev-start.sh            # start both, print the login URL
#   ./scripts/dev-start.sh --stop     # stop both
#
# Frontend: http://localhost:3000   Backend: http://127.0.0.1:5000
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PY:-$ROOT/.venv-audit/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

if [ "${1:-}" = "--stop" ]; then
  pkill -f "app.py" 2>/dev/null || true
  pkill -f "dev_frontend_server.py" 2>/dev/null || true
  echo "dev stack stopped"; exit 0
fi

export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT/autosocial_audit.db}"
export USE_MOCK_PROVIDERS=true     # no paid AI calls
export SYNC_JOBS=true              # run jobs inline, no Redis/worker needed
export FRONTEND_BASE_URL=http://localhost:3000
export API_BASE_URL=http://127.0.0.1:5000
export CORS_ORIGIN=http://localhost:3000
export SECRET_KEY="${SECRET_KEY:-dev-local-secret}"
export FACTORY_SCHEDULER_ENABLED=false
export LONGFORM_SCHEDULER_ENABLED=false

"$PY" migrations.py >/dev/null 2>&1 || true
"$PY" app.py > /tmp/dev_backend.log 2>&1 &
"$PY" scripts/dev_frontend_server.py --port 3000 --root frontend > /tmp/dev_frontend.log 2>&1 &
sleep 5

code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/api/health || echo 000)
echo "backend  : http://127.0.0.1:5000/api/health -> $code   (log: /tmp/dev_backend.log)"
echo "frontend : http://localhost:3000/login/                (log: /tmp/dev_frontend.log)"
echo "SPA deep links work: /operations, /projects/1, /create/video"
echo "stop with: ./scripts/dev-start.sh --stop"
