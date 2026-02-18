#!/usr/bin/env bash
set -euo pipefail

DATE_TAG="$(date +%Y%m%d-%H%M%S)"
REPORT_DIR="tests/reports"
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/smoke-$DATE_TAG.txt"

PROD_BASE="${PROD_BASE:-https://api.autosocial.tech}"
DEV_BASE="${DEV_BASE:-https://api-dev.autosocial.tech}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@autosocial.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin12345}"
EXPECTED_PROD_REDIRECT="${EXPECTED_PROD_REDIRECT:-https://api.autosocial.tech/api/integrations/meta/callback}"
EXPECTED_DEV_REDIRECT="${EXPECTED_DEV_REDIRECT:-https://api-dev.autosocial.tech/api/integrations/meta/callback}"

log() { echo "$*" | tee -a "$REPORT_FILE"; }

request() {
  local method="$1"; shift
  local url="$1"; shift
  local auth_token="${1:-}"
  local body="${2:-}"

  local tmp
  tmp="$(mktemp)"
  local code
  if [[ -n "$auth_token" ]]; then
    if [[ -n "$body" ]]; then
      code="$(curl -sS -o "$tmp" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $auth_token" -H "Content-Type: application/json" --data "$body")"
    else
      code="$(curl -sS -o "$tmp" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $auth_token")"
    fi
  else
    if [[ -n "$body" ]]; then
      code="$(curl -sS -o "$tmp" -w "%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" --data "$body")"
    else
      code="$(curl -sS -o "$tmp" -w "%{http_code}" -X "$method" "$url")"
    fi
  fi

  local payload
  payload="$(cat "$tmp")"
  rm -f "$tmp"
  printf '%s\n%s' "$code" "$payload"
}

extract_json_value() {
  local key="$1"
  python - "$key" <<'PY'
import json,sys
key=sys.argv[1]
raw=sys.stdin.read().strip()
try:
    data=json.loads(raw)
    val=data.get(key,"")
    print(val if val is not None else "")
except Exception:
    print("")
PY
}

login_token() {
  local base="$1"
  local result code body token
  result="$(request POST "$base/api/auth/login" "" "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")"
  code="$(echo "$result" | head -n1)"
  body="$(echo "$result" | tail -n +2)"
  if [[ "$code" == "200" ]]; then
    token="$(printf '%s' "$body" | extract_json_value token)"
    printf '%s' "$token"
  else
    printf ''
  fi
}

run_suite() {
  local env_name="$1"
  local base="$2"
  local expected_redirect="$3"

  log ""
  log "===== $env_name :: $base ====="

  local r code body

  r="$(request GET "$base/health")"; code="$(echo "$r" | head -n1)"; body="$(echo "$r" | tail -n +2)"
  log "GET /health -> $code"
  log "$body"

  local token
  token="$(login_token "$base")"
  if [[ -z "$token" ]]; then
    log "POST /api/auth/login -> FAILED (continuing with unauth checks)"
  else
    log "POST /api/auth/login -> 200 (token received)"
  fi

  if [[ -n "$token" ]]; then
    r="$(request POST "$base/api/integrations/meta/connect" "$token" "{}")"
  else
    r="$(request POST "$base/api/integrations/meta/connect" "" "{}")"
  fi
  code="$(echo "$r" | head -n1)"; body="$(echo "$r" | tail -n +2)"
  log "POST /api/integrations/meta/connect -> $code"
  log "$body"

  if [[ "$code" == "200" ]]; then
    local redirect_uri
    redirect_uri="$(printf '%s' "$body" | extract_json_value redirect_uri)"
    log "redirect_uri (response): $redirect_uri"
    if [[ -n "$expected_redirect" && "$redirect_uri" != "$expected_redirect" ]]; then
      log "WARN: redirect_uri mismatch. expected=$expected_redirect"
    fi
  fi

  local endpoints=(
    "GET /api/integrations/meta/pages"
    "POST /api/integrations/meta/select-page {\"page_id\":\"dummy\"}"
    "POST /api/integrations/meta/test-post {}"
    "POST /api/integrations/meta/disconnect {}"
  )

  for e in "${endpoints[@]}"; do
    local m path payload
    m="$(echo "$e" | awk '{print $1}')"
    path="$(echo "$e" | awk '{print $2}')"
    payload="$(echo "$e" | sed -E 's/^[A-Z]+\s+[^ ]+\s*//')"
    if [[ "$payload" == "$e" ]]; then payload=""; fi

    if [[ -n "$token" ]]; then
      r="$(request "$m" "$base$path" "$token" "$payload")"
    else
      r="$(request "$m" "$base$path" "" "$payload")"
    fi
    code="$(echo "$r" | head -n1)"; body="$(echo "$r" | tail -n +2)"
    log "$m $path -> $code"
    log "$body"
    if [[ "$code" == "404" ]]; then
      log "FAIL: endpoint returned 404 (route missing): $path"
    fi
  done
}

log "AutoSocial smoke report"
log "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

run_suite "DEV" "$DEV_BASE" "$EXPECTED_DEV_REDIRECT"
run_suite "PROD" "$PROD_BASE" "$EXPECTED_PROD_REDIRECT"

log ""
log "Report saved: $REPORT_FILE"
echo "$REPORT_FILE"
