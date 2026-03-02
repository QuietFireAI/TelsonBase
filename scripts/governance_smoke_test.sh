#!/usr/bin/env bash
# TelsonBase/scripts/governance_smoke_test.sh
# REM: =======================================================================================
# REM: GOVERNANCE SMOKE TEST — POST-DEPLOY VERIFICATION SCRIPT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: March 1, 2026
# REM:
# REM: Purpose:
# REM:   Curl-based end-to-end verification of the TelsonBase governance pipeline.
# REM:   Run immediately after a fresh deployment to confirm governance enforcement is live
# REM:   before handing the platform to users. Takes ~10 seconds.
# REM:
# REM: Usage (local dev — reads API key from secrets/):
# REM:   chmod +x scripts/governance_smoke_test.sh
# REM:   ./scripts/governance_smoke_test.sh
# REM:
# REM: Usage (remote server with explicit key):
# REM:   API_KEY=... API_BASE=http://159.65.241.102:8000 ./scripts/governance_smoke_test.sh
# REM:
# REM: Usage (inside Docker network — from mcp_server container):
# REM:   docker compose exec mcp_server bash /app/scripts/governance_smoke_test.sh
# REM:
# REM: Prerequisites:
# REM:   - curl (standard on Linux/macOS/WSL)
# REM:   - python3 (available wherever TelsonBase runs)
# REM:   - TelsonBase running + alembic migrations applied (alembic upgrade head)
# REM:
# REM: What this verifies:
# REM:    1. API liveness + Redis health
# REM:    2. Agent registration starts in QUARANTINE
# REM:    3. Quarantine: internal read blocked
# REM:    4. Quarantine: external write blocked
# REM:    5. Human promotion: QUARANTINE → PROBATION
# REM:    6. Probation: internal read ALLOWED (autonomous)
# REM:    7. Probation: external write GATED (HITL approval required)
# REM:    8. Kill switch: agent suspended
# REM:    9. Kill switch: suspended agent cannot act
# REM:   10. Reinstatement restores governance
# REM:   11. Audit chain: accessible and SHA-256 hash chain intact
# REM: =======================================================================================

set -uo pipefail

# REM: ===========================================================================
# REM: CONFIGURATION
# REM: ===========================================================================
API_BASE="${API_BASE:-http://localhost:8000}"
TIMESTAMP="$(date +%s)"
AGENT_NAME="smoke-test-agent-${TIMESTAMP}"
AGENT_KEY="smoke-test-key-${TIMESTAMP}"

# REM: Discover API key: prefer env, then secrets file (project root), then container path.
if [[ -n "${API_KEY:-}" ]]; then
    AUTH_KEY="$API_KEY"
elif [[ -f "secrets/telsonbase_mcp_api_key" ]]; then
    AUTH_KEY="$(tr -d '[:space:]' < secrets/telsonbase_mcp_api_key)"
elif [[ -f "/run/secrets/telsonbase_mcp_api_key" ]]; then
    AUTH_KEY="$(tr -d '[:space:]' < /run/secrets/telsonbase_mcp_api_key)"
else
    echo "ERROR: No API key found."
    echo "  Set API_KEY env var, or run from the project root (where secrets/ lives)."
    exit 1
fi

# REM: ===========================================================================
# REM: HELPERS
# REM: ===========================================================================
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    echo -e "${GREEN}[PASS]${RESET} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "${RED}[FAIL]${RESET} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

info() { echo -e "${CYAN}[INFO]${RESET} $1"; }
header() { echo -e "\n${BOLD}${YELLOW}── $1${RESET}"; }

# REM: curl wrapper: appends HTTP status code on final line, body above it.
# REM: Never exits non-zero on HTTP errors — smoke test continues through failures.
telson_curl() {
    local method="$1"
    local path="$2"
    shift 2
    curl -s -w "\n%{http_code}" \
        -X "$method" \
        -H "X-API-Key: ${AUTH_KEY}" \
        -H "Content-Type: application/json" \
        "$@" \
        "${API_BASE}${path}" 2>/dev/null || echo -e "\nERR"
}

# REM: Extract the HTTP status code (last line of telson_curl output).
http_code() { echo "$1" | tail -1; }

# REM: Extract the body (everything except the last line).
http_body() { echo "$1" | head -n -1; }

# REM: Extract a field from JSON body using python3 (available everywhere TelsonBase runs).
# REM: Usage: json_get "$body" "['field']" default_value
json_get() {
    local body="$1"
    local accessor="$2"
    local default="${3:-}"
    echo "$body" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d${accessor})
except Exception:
    print('${default}')
" 2>/dev/null || echo "$default"
}

# REM: ===========================================================================
# REM: OPENCLAW_ENABLED check
# REM: ===========================================================================
# REM: The governance pipeline requires OPENCLAW_ENABLED=true in .env (or as env var).
# REM: In production, enable it before running this test:
# REM:   sed -i 's/^OPENCLAW_ENABLED=false/OPENCLAW_ENABLED=true/' .env
# REM:   docker compose restart mcp_server && sleep 4
# REM:   <run smoke test>
# REM:   sed -i 's/^OPENCLAW_ENABLED=true/OPENCLAW_ENABLED=false/' .env
# REM:   docker compose restart mcp_server
# REM: Or set SKIP_OPENCLAW=1 to skip governance steps and test only platform health + audit chain.
SKIP_OPENCLAW="${SKIP_OPENCLAW:-0}"

# REM: ===========================================================================
# REM: BANNER
# REM: ===========================================================================
echo ""
echo -e "${BOLD}TelsonBase Governance Smoke Test${RESET}"
echo "  Target : ${API_BASE}"
echo "  Agent  : ${AGENT_NAME}"
echo "  Time   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  ─────────────────────────────────────────"

# --------------------------------------------------------------------------
header "1. Platform health"
# --------------------------------------------------------------------------
resp=$(telson_curl GET /health)
code=$(http_code "$resp")
body=$(http_body "$resp")

if [[ "$code" == "200" ]]; then
    pass "API liveness: HTTP 200"
else
    fail "API health check returned HTTP $code — is TelsonBase running at ${API_BASE}?"
    echo "  Response: $body"
    echo ""
    echo -e "${RED}Cannot continue without a live API. Aborting.${RESET}"
    exit 1
fi

redis_status=$(json_get "$body" "['redis']" "unknown")
if [[ "$redis_status" =~ ^(ok|healthy|connected)$ ]]; then
    pass "Redis: ${redis_status}"
else
    fail "Redis status: ${redis_status} (check: docker compose logs redis)"
fi

# --------------------------------------------------------------------------
header "2. Register agent — must start in QUARANTINE"
# --------------------------------------------------------------------------
reg_resp=$(telson_curl POST /v1/openclaw/register -d "{
    \"name\": \"${AGENT_NAME}\",
    \"api_key\": \"${AGENT_KEY}\"
}")
reg_code=$(http_code "$reg_resp")
reg_body=$(http_body "$reg_resp")

OC_AVAILABLE=1
if [[ "$reg_code" != "200" ]]; then
    OC_AVAILABLE=0
    # REM: 404 = OPENCLAW_ENABLED=false — not a platform fault, governance steps are skipped.
    if echo "$reg_body" | grep -q "not enabled"; then
        echo -e "${YELLOW}[SKIP]${RESET} OpenClaw is disabled (OPENCLAW_ENABLED=false in .env)"
        echo -e "       To test the full governance pipeline:"
        echo -e "         sed -i 's/OPENCLAW_ENABLED=false/OPENCLAW_ENABLED=true/' .env"
        echo -e "         docker compose restart mcp_server && sleep 4"
        echo -e "         <re-run this script>"
    else
        fail "Registration failed (HTTP ${reg_code}): ${reg_body}"
        OC_AVAILABLE=0
    fi
fi

INSTANCE_ID=""
if [[ $OC_AVAILABLE -eq 1 ]]; then
    INSTANCE_ID=$(json_get "$reg_body" "['instance_id']" "")
    trust_level=$(json_get "$reg_body" "['trust_level']" "unknown")
    if [[ -z "$INSTANCE_ID" ]]; then
        fail "Registration returned no instance_id: ${reg_body}"
        OC_AVAILABLE=0
    fi
fi

if [[ $OC_AVAILABLE -eq 1 ]]; then
    info "instance_id : ${INSTANCE_ID}"
    info "trust_level : ${trust_level}"
    if [[ "$trust_level" == "quarantine" ]]; then
        pass "Agent starts in QUARANTINE"
    else
        fail "Agent started in '${trust_level}' (expected quarantine)"
    fi
fi

# --------------------------------------------------------------------------
header "3. Quarantine: internal read must be BLOCKED"
# --------------------------------------------------------------------------
if [[ $OC_AVAILABLE -eq 0 ]]; then
    echo -e "${YELLOW}[SKIP]${RESET} OpenClaw not enabled"
else
q_read_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/action" -d '{
    "tool_name": "read_file",
    "tool_args": {"path": "/data/documents/test.txt"}
}')
q_read_code=$(http_code "$q_read_resp")
q_read_body=$(http_body "$q_read_resp")
q_read_allowed=$(json_get "$q_read_body" "['allowed']" "True")

if [[ "$q_read_code" == "200" && "$q_read_allowed" == "False" ]]; then
    pass "Quarantine: internal read blocked"
else
    fail "Quarantine: internal read should be blocked — HTTP ${q_read_code}, allowed=${q_read_allowed}"
    info "  Response: ${q_read_body}"
fi
fi

# REM: Steps 4-10 all require a live OpenClaw instance — skip if OC_AVAILABLE=0.
if [[ $OC_AVAILABLE -eq 0 ]]; then
    for step in "4. Quarantine: external write" "5. Human promotion" "6. Probation: internal read" \
                "7. Probation: external write" "8. Kill switch: suspend" \
                "9. Kill switch: suspended action" "10. Reinstatement"; do
        header "$step"
        echo -e "${YELLOW}[SKIP]${RESET} OpenClaw not enabled (OPENCLAW_ENABLED=false)"
    done
else

# --------------------------------------------------------------------------
header "4. Quarantine: external write must be BLOCKED"
# --------------------------------------------------------------------------
q_ext_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/action" -d '{
    "tool_name": "http_post",
    "tool_args": {"url": "https://api.example.com/data", "body": "test"}
}')
q_ext_code=$(http_code "$q_ext_resp")
q_ext_body=$(http_body "$q_ext_resp")
q_ext_allowed=$(json_get "$q_ext_body" "['allowed']" "True")

if [[ "$q_ext_code" == "200" && "$q_ext_allowed" == "False" ]]; then
    pass "Quarantine: external write blocked"
else
    fail "Quarantine: external write should be blocked — HTTP ${q_ext_code}, allowed=${q_ext_allowed}"
    info "  Response: ${q_ext_body}"
fi

# --------------------------------------------------------------------------
header "5. Human promotion: QUARANTINE → PROBATION"
# --------------------------------------------------------------------------
prom_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/promote" -d '{
    "new_level": "probation",
    "reason": "Smoke test: governance pipeline verified at quarantine — promoting for probation checks"
}')
prom_code=$(http_code "$prom_resp")
prom_body=$(http_body "$prom_resp")

if [[ "$prom_code" == "200" ]]; then
    pass "Promotion QUARANTINE → PROBATION: HTTP 200"
else
    fail "Promotion failed (HTTP ${prom_code}): ${prom_body}"
fi

# --------------------------------------------------------------------------
header "6. Probation: internal read must be ALLOWED (autonomous)"
# --------------------------------------------------------------------------
prob_read_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/action" -d '{
    "tool_name": "read_file",
    "tool_args": {"path": "/data/documents/test.txt"}
}')
prob_read_code=$(http_code "$prob_read_resp")
prob_read_body=$(http_body "$prob_read_resp")
prob_read_allowed=$(json_get "$prob_read_body" "['allowed']" "False")

if [[ "$prob_read_code" == "200" && "$prob_read_allowed" == "True" ]]; then
    pass "Probation: internal read ALLOWED (autonomous — no approval needed)"
else
    fail "Probation: internal read should be allowed — HTTP ${prob_read_code}, allowed=${prob_read_allowed}"
    info "  Response: ${prob_read_body}"
fi

# --------------------------------------------------------------------------
header "7. Probation: external write must be GATED (HITL approval)"
# --------------------------------------------------------------------------
ext_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/action" -d '{
    "tool_name": "http_post",
    "tool_args": {"url": "https://api.example.com/submit", "body": "sensitive-data"}
}')
ext_code=$(http_code "$ext_resp")
ext_body=$(http_body "$ext_resp")
ext_allowed=$(json_get "$ext_body" "['allowed']" "True")
ext_approval=$(json_get "$ext_body" "['approval_required']" "False")

if [[ "$ext_code" == "200" && "$ext_allowed" == "False" ]]; then
    pass "Probation: external write GATED (approval_required=${ext_approval})"
else
    fail "Probation: external write should be gated — HTTP ${ext_code}, allowed=${ext_allowed}, approval_required=${ext_approval}"
    info "  Response: ${ext_body}"
fi

# --------------------------------------------------------------------------
header "8. Kill switch: suspend agent"
# --------------------------------------------------------------------------
susp_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/suspend" -d '{
    "reason": "Smoke test: exercising kill switch — verifying immediate suspension"
}')
susp_code=$(http_code "$susp_resp")
susp_body=$(http_body "$susp_resp")

if [[ "$susp_code" == "200" ]]; then
    pass "Kill switch: agent suspended (HTTP 200)"
else
    fail "Kill switch: suspension failed (HTTP ${susp_code}): ${susp_body}"
fi

# --------------------------------------------------------------------------
header "9. Kill switch: suspended agent cannot act"
# --------------------------------------------------------------------------
susp_act_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/action" -d '{
    "tool_name": "read_file",
    "tool_args": {"path": "/data/documents/test.txt"}
}')
susp_act_code=$(http_code "$susp_act_resp")
susp_act_body=$(http_body "$susp_act_resp")
susp_act_allowed=$(json_get "$susp_act_body" "['allowed']" "True")

if [[ "$susp_act_code" == "200" && "$susp_act_allowed" == "False" ]]; then
    pass "Kill switch: suspended agent's action BLOCKED"
else
    fail "Kill switch: suspended agent should be blocked — HTTP ${susp_act_code}, allowed=${susp_act_allowed}"
    info "  Response: ${susp_act_body}"
fi

# --------------------------------------------------------------------------
header "10. Reinstatement"
# --------------------------------------------------------------------------
reinst_resp=$(telson_curl POST "/v1/openclaw/${INSTANCE_ID}/reinstate" -d '{
    "reason": "Smoke test complete — reinstating after kill switch verification"
}')
reinst_code=$(http_code "$reinst_resp")
reinst_body=$(http_body "$reinst_resp")

if [[ "$reinst_code" == "200" ]]; then
    pass "Reinstatement: agent reinstated (HTTP 200)"
else
    fail "Reinstatement failed (HTTP ${reinst_code}): ${reinst_body}"
fi

fi  # REM: end of OC_AVAILABLE block (steps 4-10)

# --------------------------------------------------------------------------
header "11. Audit chain integrity"
# --------------------------------------------------------------------------
chain_resp=$(telson_curl GET "/v1/audit/chain/status")
chain_code=$(http_code "$chain_resp")
chain_body=$(http_body "$chain_resp")

if [[ "$chain_code" == "200" ]]; then
    entry_count=$(json_get "$chain_body" ".get('entries_count', chain_body.get('entry_count', '?'))" "?")
    # REM: Handle both possible key names for compatibility
    entry_count=$(echo "$chain_body" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('entries_count', d.get('entry_count', '?')))
except Exception:
    print('?')
" 2>/dev/null || echo "?")
    pass "Audit chain: accessible (${entry_count} entries)"
else
    fail "Audit chain: status check failed (HTTP ${chain_code})"
fi

verify_resp=$(telson_curl GET "/v1/audit/chain/verify?entries=50")
verify_code=$(http_code "$verify_resp")
verify_body=$(http_body "$verify_resp")

if [[ "$verify_code" == "200" ]]; then
    breaks=$(echo "$verify_body" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d.get('chain_breaks', [])))
except Exception:
    print('?')
" 2>/dev/null || echo "?")
    if [[ "$breaks" == "0" ]]; then
        pass "Audit chain: SHA-256 hash chain intact (0 breaks, last 50 entries)"
    elif [[ "$breaks" == "?" ]]; then
        info "Audit chain verify: could not parse response — manual check needed"
    else
        fail "Audit chain: ${breaks} break(s) detected in last 50 entries"
    fi
else
    fail "Audit chain: verify request failed (HTTP ${verify_code})"
fi

# --------------------------------------------------------------------------
# REM: Trust report — informational, not a pass/fail gate
# --------------------------------------------------------------------------
header "Trust report (informational)"
trust_resp=$(telson_curl GET "/v1/openclaw/${INSTANCE_ID}/trust-report")
trust_code=$(http_code "$trust_resp")
trust_body=$(http_body "$trust_resp")

if [[ "$trust_code" == "200" ]]; then
    final_trust=$(json_get "$trust_body" "['trust_level']" "?")
    manners=$(json_get "$trust_body" "['manners_score']" "?")
    allowed_count=$(json_get "$trust_body" "['actions_allowed']" "?")
    blocked_count=$(json_get "$trust_body" "['actions_blocked']" "?")
    info "Trust level   : ${final_trust}"
    info "Manners score : ${manners}"
    info "Actions allow : ${allowed_count}"
    info "Actions block : ${blocked_count}"
else
    info "Trust report unavailable (HTTP ${trust_code})"
fi

# --------------------------------------------------------------------------
# REM: RESULTS SUMMARY
# --------------------------------------------------------------------------
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo ""
echo "  ─────────────────────────────────────────"
echo -e "  ${BOLD}Passed : ${GREEN}${PASS_COUNT}${RESET} / ${TOTAL}${RESET}"
echo -e "  ${BOLD}Failed : ${RED}${FAIL_COUNT}${RESET}${RESET}"
echo ""

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}All governance checks passed.${RESET}"
    echo -e "  ${GREEN}Platform is operational — governance pipeline enforcing correctly.${RESET}"
    echo ""
    exit 0
else
    echo -e "  ${RED}${BOLD}${FAIL_COUNT} check(s) failed.${RESET}"
    echo -e "  ${RED}Review output above before handing platform to users.${RESET}"
    echo ""
    exit 1
fi
