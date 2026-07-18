#!/usr/bin/env bash
# Frontend integrity gate. Run before any deployment of frontend/app.js.
# Fails (exit 1) on: JS syntax errors, UTF-8 decode errors, or suspicious
# mojibake (long runs of '?' that indicate a corrupted Unicode transfer).
set -euo pipefail
cd "$(dirname "$0")/.."
FILE=frontend/app.js

node -e "new Function(require('fs').readFileSync('$FILE','utf8'))" \
  || { echo "FAIL: JavaScript syntax error in $FILE"; exit 1; }

python3 -c "open('$FILE', encoding='utf-8').read()" \
  || { echo "FAIL: $FILE is not valid UTF-8"; exit 1; }

# '????' sequences almost never appear in legitimate code; > 3 of them is a
# strong signal of the mojibake corruption seen previously in production.
COUNT=$(grep -o '????' "$FILE" | wc -l | tr -d ' ')
if [ "$COUNT" -gt 3 ]; then
  echo "FAIL: $FILE contains $COUNT '????' sequences (possible Unicode corruption)"
  exit 1
fi

shasum -a 256 "$FILE"
echo "OK: $FILE passed syntax, UTF-8 and corruption checks"
