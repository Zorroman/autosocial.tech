#!/usr/bin/env bash
# Pre-deploy gate. Run from the repo root before ANY production deployment.
# Stops on the first failure. Never copies .env or runtime output.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1. git working tree =="
if [ -n "$(git status --porcelain)" ]; then
  echo "FAIL: working tree is dirty. Commit or stash before deploying."
  exit 1
fi
git log -1 --oneline

echo "== 2/3/4. frontend integrity (UTF-8, JS syntax, mojibake) =="
bash scripts/check_frontend_integrity.sh

echo "== 5. python syntax =="
python3 - <<'PY'
import ast, glob
for f in glob.glob("*.py"):
    ast.parse(open(f, encoding="utf-8-sig").read(), filename=f)
print("python syntax OK")
PY

echo "== 6. critical tests =="
python -m pytest tests/test_private_admin.py tests/test_video_projects.py \
  tests/test_publications.py tests/test_analytics_costs.py \
  tests/test_factory_dashboard.py tests/test_render_fixture.py -q

echo "== 6b. git diff --check =="
git diff --check
git diff --cached --check

echo "== 7. migrations check (dry import) =="
python3 -c "import migrations; print('migrations module OK (applied automatically on app start)')"

echo "== 8/9. deploy hygiene reminders =="
echo " - NEVER copy .env to or from the server via this script"
echo " - NEVER rsync output/, data/, cache/, generated_media/, logs/"
echo " - use: rsync -a --checksum --exclude-from=.gitignore ..."

echo ""
echo "ALL PRE-DEPLOY CHECKS PASSED"
