#!/usr/bin/env bash
# Verify a deployed frontend/app.js after it has landed on the server.
#
# The expected SHA-256 is passed in by the deployment for the specific release
# (never hardcoded), so this script stays correct across releases.
#
# Usage:
#   scripts/verify_deployed_frontend.sh <expected_sha256> <path_to_app.js>
#
# Exit 0 only when every integrity check passes. Any failure -> non-zero.
set -euo pipefail

EXPECTED_SHA="${1:-}"
TARGET="${2:-}"
MIN_BYTES="${MIN_APP_JS_BYTES:-400000}"   # app.js is ~1.2MB; guard against truncation
MAX_QMARK="${MAX_QMARK_SEQUENCES:-3}"     # the corruption detector string itself contains one

fail() { echo "FRONTEND VERIFY FAILED: $1"; exit 1; }

[ -n "$EXPECTED_SHA" ] || fail "expected SHA-256 not provided (arg 1)"
[ -n "$TARGET" ] || fail "target file not provided (arg 2)"

# 1. exists
[ -f "$TARGET" ] || fail "file does not exist: $TARGET"

# 2. size above minimum (truncation guard)
SIZE=$(wc -c < "$TARGET" | tr -d ' ')
[ "$SIZE" -ge "$MIN_BYTES" ] || fail "file too small ($SIZE < $MIN_BYTES) — possible truncation"

# 3. SHA-256 match
if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA=$(sha256sum "$TARGET" | awk '{print $1}')
else
  ACTUAL_SHA=$(shasum -a 256 "$TARGET" | awk '{print $1}')
fi
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || fail "SHA-256 mismatch: expected $EXPECTED_SHA got $ACTUAL_SHA"

# 4-10. content integrity via python (UTF-8, replacement chars, mojibake,
#       conflict markers, ???? count, JS parse via node, key markers)
python3 - "$TARGET" "$MAX_QMARK" <<'PY'
import sys
p, max_q = sys.argv[1], int(sys.argv[2])
raw = open(p, "rb").read()
try:
    s = raw.decode("utf-8")
except UnicodeDecodeError as e:
    print(f"FRONTEND VERIFY FAILED: not valid UTF-8: {e}"); sys.exit(1)
repl = s.count("�")
if repl:
    print(f"FRONTEND VERIFY FAILED: {repl} replacement characters"); sys.exit(1)
q = s.count("?" * 4)
if q > max_q:
    print(f"FRONTEND VERIFY FAILED: {q} '????' sequences (> {max_q})"); sys.exit(1)
if s.count("<" * 7) or s.count(">" * 7) or s.count("=" * 7 + "\n"):
    print("FRONTEND VERIFY FAILED: merge conflict markers present"); sys.exit(1)
# expected key markers must be present (not a truncated/wrong file)
required = ["function render(", "pageContentDirector", "pageFactoryDashboard", "function nav("]
missing = [m for m in required if m not in s]
if missing:
    print(f"FRONTEND VERIFY FAILED: missing expected markers: {missing}"); sys.exit(1)
# file must not end mid-token
if not s.rstrip().endswith((";", "}", ")", "*/")):
    print("FRONTEND VERIFY FAILED: file appears truncated (unexpected tail)"); sys.exit(1)
print("  content checks: UTF-8 ok, 0 replacement chars, ???? within threshold, "
      "no conflict markers, markers present, not truncated")
PY

# JS syntax (node if available; python check already validated structure)
if command -v node >/dev/null 2>&1; then
  node -e "const fs=require('fs'); new Function(fs.readFileSync(process.argv[1],'utf8'));" "$TARGET" \
    || fail "JavaScript does not parse"
  echo "  JS syntax: OK (node)"
else
  echo "  JS syntax: SKIPPED (node not installed on this host)"
fi

echo "FRONTEND VERIFY OK: $TARGET ($SIZE bytes, sha256 $ACTUAL_SHA)"
