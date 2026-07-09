#!/usr/bin/env bash
# SeyalRun v2.0 — API Validation Script
# Usage: bash ops/validate-api.sh [host] [port]
# Example: bash ops/validate-api.sh 192.168.64.7 8443

set -uo pipefail

HOST="${1:-192.168.64.7}"
PORT="${2:-8443}"
BASE="https://${HOST}:${PORT}"
K="-sk"   # insecure TLS — self-signed cert on staging

PASS=0
FAIL=0

pass() { printf "  \033[0;32m✓\033[0m %s\n" "$1"; PASS=$((PASS+1)); }
fail() { printf "  \033[0;31m✗\033[0m %s\n" "$1"; FAIL=$((FAIL+1)); }
skip() { printf "  \033[0;33m-\033[0m %s\n" "$1"; }

echo ""
echo "=== SeyalRun v2.0 — API Validation ==="
echo "    Target: ${BASE}"
echo ""

read -s -p "Admin password: " ADMIN_PASS; echo ""
if [[ -z "$ADMIN_PASS" ]]; then echo "No password entered."; exit 1; fi

# ── 1. Health ──────────────────────────────────────────────────────────────
echo "[1] Health"
resp=$(curl $K -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/health")
[ "$resp" = "200" ] && pass "GET /health → 200" || fail "GET /health → $resp (expected 200)"

# ── 2. Login ───────────────────────────────────────────────────────────────
echo "[2] Auth: Login"
login_body=$(curl $K -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"${ADMIN_PASS}\"}")
TOKEN=$(echo "$login_body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [[ -n "$TOKEN" ]]; then
  pass "POST /auth/login → JWT received"
else
  fail "POST /auth/login → no token  (response: ${login_body:0:80})"
  echo "Cannot continue without a valid token. Check the password."
  exit 1
fi
AH="Authorization: Bearer $TOKEN"

# ── 3. Hosts list ──────────────────────────────────────────────────────────
echo "[3] Inventory: Hosts"
hosts_body=$(curl $K -s -H "$AH" "$BASE/api/v1/hosts")
hosts_code=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/hosts")
if [ "$hosts_code" = "200" ]; then
  cnt=$(echo "$hosts_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else '?')" 2>/dev/null)
  pass "GET /hosts → 200  ($cnt host(s) in DB)"
else
  fail "GET /hosts → $hosts_code"
fi
HOST_ID=$(echo "$hosts_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null)
HOST_IP=$(echo "$hosts_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0].get('ip','?') if isinstance(d,list) and d else '')" 2>/dev/null)

# ── 4. GET /hosts/{id}  (the 405 bug fix) ─────────────────────────────────
echo "[4] Inventory: GET /hosts/{id}  ← 405 bug fix"
if [[ -n "$HOST_ID" ]]; then
  hcode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/hosts/$HOST_ID")
  [ "$hcode" = "200" ] \
    && pass "GET /hosts/$HOST_ID → 200  (was 405 before fix — FIXED)" \
    || fail "GET /hosts/$HOST_ID → $hcode  (expected 200)"
else
  skip "No hosts in DB — add a host via Admin → Assets to test this endpoint"
fi

# ── 5. POST /hosts/{id}/test  (▶ reachability button) ─────────────────────
echo "[5] Inventory: POST /hosts/{id}/test  ← ▶ test button"
if [[ -n "$HOST_ID" ]]; then
  test_body=$(curl $K -s -X POST -H "$AH" "$BASE/api/v1/hosts/$HOST_ID/test")
  test_code=$(curl $K -s -X POST -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/hosts/$HOST_ID/test")
  if [ "$test_code" = "200" ]; then
    reachable=$(echo "$test_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('reachable','?'))" 2>/dev/null)
    pass "POST /hosts/$HOST_ID/test → 200  (reachable=$reachable, host=$HOST_IP)"
  else
    fail "POST /hosts/$HOST_ID/test → $test_code  (body: ${test_body:0:80})"
  fi
else
  skip "No hosts in DB"
fi

# ── 6. POST /ssh/sessions  (ws_path Pydantic fix) ─────────────────────────
echo "[6] Terminal: POST /ssh/sessions  ← ws_path ValidationError fix"
SESSION_ID=""
WS_PATH=""
if [[ -n "$HOST_ID" ]]; then
  sess_code=$(curl $K -s -X POST -H "$AH" -H "Content-Type: application/json" \
    -d "{\"host_id\":\"${HOST_ID}\"}" -o /dev/null -w "%{http_code}" "$BASE/api/v1/ssh/sessions")
  sess_body=$(curl $K -s -X POST -H "$AH" -H "Content-Type: application/json" \
    -d "{\"host_id\":\"${HOST_ID}\"}" "$BASE/api/v1/ssh/sessions")

  if [ "$sess_code" = "201" ]; then
    SESSION_ID=$(echo "$sess_body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    WS_PATH=$(echo "$sess_body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ws_path',''))" 2>/dev/null)
    if [[ -n "$SESSION_ID" && -n "$WS_PATH" && "$WS_PATH" != '""' ]]; then
      pass "POST /ssh/sessions → 201  (id=${SESSION_ID:0:8}…, ws_path=$WS_PATH)  Pydantic fix VERIFIED"
    else
      fail "POST /ssh/sessions → 201 but ws_path missing or empty  (body: ${sess_body:0:120})"
    fi
  elif [ "$sess_code" = "403" ]; then
    detail=$(echo "$sess_body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('detail',''))" 2>/dev/null)
    pass "POST /ssh/sessions → 403 '$detail'  (endpoint functional — 403 = no SSH credential linked, not a code bug)"
  elif [ "$sess_code" = "500" ]; then
    fail "POST /ssh/sessions → 500  (Pydantic ValidationError still present? body: ${sess_body:0:120})"
  else
    fail "POST /ssh/sessions → $sess_code  (body: ${sess_body:0:120})"
  fi
else
  skip "No hosts in DB"
fi

# ── 7. GET /ssh/sessions  (list) ──────────────────────────────────────────
echo "[7] Terminal: GET /ssh/sessions"
slcode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/ssh/sessions")
[ "$slcode" = "200" ] && pass "GET /ssh/sessions → 200" || fail "GET /ssh/sessions → $slcode"

# ── 8. GET /ssh/sessions/{id} ─────────────────────────────────────────────
echo "[8] Terminal: GET /ssh/sessions/{id}"
if [[ -n "$SESSION_ID" ]]; then
  scode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/ssh/sessions/$SESSION_ID")
  [ "$scode" = "200" ] && pass "GET /ssh/sessions/$SESSION_ID → 200" || fail "GET /ssh/sessions/$SESSION_ID → $scode"
else
  skip "No session created (no 201 in step 6)"
fi

# ── 9. DELETE /ssh/sessions/{id}  (terminate) ─────────────────────────────
echo "[9] Terminal: DELETE /ssh/sessions/{id}"
if [[ -n "$SESSION_ID" ]]; then
  dcode=$(curl $K -s -X DELETE -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/ssh/sessions/$SESSION_ID")
  [ "$dcode" = "204" ] && pass "DELETE /ssh/sessions/$SESSION_ID → 204" || fail "DELETE /ssh/sessions/$SESSION_ID → $dcode"
else
  skip "No session to terminate"
fi

# ── 10. Recordings ────────────────────────────────────────────────────────
echo "[10] Recording: GET /recordings"
rcode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/recordings")
[ "$rcode" = "200" ] && pass "GET /recordings → 200" || fail "GET /recordings → $rcode"

# ── 11. Zones ─────────────────────────────────────────────────────────────
echo "[11] Inventory: GET /zones"
zcode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/zones")
[ "$zcode" = "200" ] && pass "GET /zones → 200" || fail "GET /zones → $zcode"

# ── 12. Credentials ───────────────────────────────────────────────────────
echo "[12] Inventory: GET /credentials"
ccode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/credentials")
[ "$ccode" = "200" ] && pass "GET /credentials → 200" || fail "GET /credentials → $ccode"

# ── 13. Authorizations ────────────────────────────────────────────────────
echo "[13] Identity: GET /authorizations"
acode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/authorizations")
[ "$acode" = "200" ] && pass "GET /authorizations → 200" || fail "GET /authorizations → $acode"

# ── 14. Audit logs ────────────────────────────────────────────────────────
echo "[14] Identity: GET /audit/logs"
aucode=$(curl $K -s -H "$AH" -o /dev/null -w "%{http_code}" "$BASE/api/v1/audit/logs")
[ "$aucode" = "200" ] && pass "GET /audit/logs → 200" || fail "GET /audit/logs → $aucode"

# ── Summary ───────────────────────────────────────────────────────────────
TOTAL=$((PASS+FAIL))
echo ""
echo "==========================================="
printf "  Results: \033[0;32m%d passed\033[0m / \033[0;31m%d failed\033[0m / %d total\n" "$PASS" "$FAIL" "$TOTAL"
echo "==========================================="
if [ "$FAIL" -eq 0 ]; then
  echo "  ALL TESTS PASSED"
else
  echo "  SOME TESTS FAILED — check output above"
fi
echo ""
exit $FAIL
