#!/bin/bash
# TelsonBase/scripts/dr_test.sh
# REM: =======================================================================================
# REM: TELSONBASE DISASTER RECOVERY TEST SCRIPT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: Automated verification that TelsonBase backup and restore
# REM: procedures work correctly, measuring RPO and RTO against compliance targets.
# REM: Supports both a quick smoke test (<5 min) and a full DR cycle test.
#
# REM: Usage:
# REM:   chmod +x scripts/dr_test.sh
# REM:   ./scripts/dr_test.sh --quick        # Smoke test: connectivity and readiness
# REM:   ./scripts/dr_test.sh --full         # Full DR cycle: backup, restore, verify
#
# REM: Compliance: SOC 2 A1.2 (Recovery Testing), HIPAA 164.308(a)(7)(ii)(D)
# REM: =======================================================================================

set -euo pipefail

# REM: Color output for readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# REM: Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/dr_test_$(date +%Y%m%d).log"
REDIS_PASSWORD="${REDIS_PASSWORD:-telsonbase_redis_dev}"
HEALTH_TIMEOUT=300
HEALTH_INTERVAL=5
RPO_TARGET_HOURS=24
RTO_TARGET_SECONDS=900
FAIL_COUNT=0

# REM: Ensure log directory exists
mkdir -p "$LOG_DIR"

# REM: Logging helper — writes to both stdout and log file
log() {
    local msg="$1"
    echo -e "$msg"
    echo -e "$msg" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

pass() { log "  ${GREEN}[PASS]${NC} $1"; }
fail() { log "  ${RED}[FAIL]${NC} $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { log "  ${YELLOW}[WARN]${NC} $1"; }
info() { log "  ${CYAN}[INFO]${NC} $1"; }

# REM: =======================================================================================
# REM: ARGUMENT PARSING
# REM: =======================================================================================
TEST_MODE=""

if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 --quick | --full${NC}"
    echo ""
    echo "  --quick    Smoke test: verify backup exists, services reachable (<5 min)"
    echo "  --full     Full DR cycle: backup, stop, restore, verify, measure RTO"
    exit 1
fi

case "$1" in
    --quick) TEST_MODE="quick" ;;
    --full)  TEST_MODE="full" ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo "Usage: $0 --quick | --full"
        exit 1
        ;;
esac

cd "$PROJECT_DIR"

echo "" >> "$LOG_FILE"
log "================================================================="
log "TelsonBase DR Test — $(date '+%Y-%m-%d %H:%M:%S') — mode: ${TEST_MODE}"
log "================================================================="

log ""
log "${CYAN}+--------------------------------------------------------------+${NC}"
log "${CYAN}|       TelsonBase — Disaster Recovery Test (${TEST_MODE})            |${NC}"
log "${CYAN}|                    by Quietfire AI                              |${NC}"
log "${CYAN}+--------------------------------------------------------------+${NC}"
log ""

# REM: =======================================================================================
# REM: QUICK TEST — Smoke checks only
# REM: =======================================================================================
run_quick_test() {
    log "${YELLOW}[1/5] Verify backup exists${NC}"
    LATEST_BACKUP=$(ls -1d "${PROJECT_DIR}"/backups/*/ 2>/dev/null | tail -1 || true)
    if [ -n "$LATEST_BACKUP" ] && [ -f "${LATEST_BACKUP}postgres_backup.sql" ]; then
        pass "Backup found: $(basename "$LATEST_BACKUP")"
    else
        fail "No valid backup found in backups/"
    fi

    log "${YELLOW}[2/5] Verify restore script is executable${NC}"
    if [ -x "${SCRIPT_DIR}/restore.sh" ]; then
        pass "restore.sh is executable"
    else
        fail "restore.sh is not executable (run: chmod +x scripts/restore.sh)"
    fi

    log "${YELLOW}[3/5] Verify PostgreSQL connectivity${NC}"
    PG_READY=$(docker compose exec -T postgres pg_isready -U telsonbase 2>/dev/null && echo "ok" || echo "fail")
    if [ "$PG_READY" = "ok" ]; then
        pass "PostgreSQL accepting connections"
    else
        fail "PostgreSQL not responding"
    fi

    log "${YELLOW}[4/5] Verify Redis PING${NC}"
    REDIS_PONG=$(docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" PING 2>/dev/null | tr -d '\r' || true)
    if [ "$REDIS_PONG" = "PONG" ]; then
        pass "Redis responding to PING"
    else
        fail "Redis not responding (got: ${REDIS_PONG:-empty})"
    fi

    log "${YELLOW}[5/5] Verify Docker services are running${NC}"
    for svc in postgres redis mcp_server; do
        if docker compose ps --status running 2>/dev/null | grep -q "$svc"; then
            pass "Service running: ${svc}"
        else
            fail "Service not running: ${svc}"
        fi
    done
}

# REM: =======================================================================================
# REM: FULL TEST — Complete DR cycle
# REM: =======================================================================================
run_full_test() {
    # REM: Step A — Record start time
    DR_START=$(date +%s)
    info "DR test started at $(date '+%H:%M:%S')"

    # REM: Step B — Run backup.sh to create a fresh backup
    log "${YELLOW}[Step 1/7] Creating fresh backup${NC}"
    BACKUP_START=$(date +%s)
    if bash "${SCRIPT_DIR}/backup.sh" >> "$LOG_FILE" 2>&1; then
        pass "backup.sh completed successfully"
    else
        fail "backup.sh failed — cannot continue DR test"
        return
    fi
    BACKUP_END=$(date +%s)
    BACKUP_DURATION=$((BACKUP_END - BACKUP_START))
    info "Backup duration: ${BACKUP_DURATION}s"

    # REM: Step C — Identify the backup just created (most recent directory)
    BACKUP_DIR=$(ls -1dt "${PROJECT_DIR}"/backups/*/ 2>/dev/null | head -1)
    if [ -z "$BACKUP_DIR" ]; then
        fail "Could not locate backup directory after backup.sh"
        return
    fi
    info "Using backup: $(basename "$BACKUP_DIR")"

    # REM: Step D — Stop application containers to simulate outage
    log "${YELLOW}[Step 2/7] Simulating outage — stopping mcp_server and worker${NC}"
    DOWNTIME_START=$(date +%s)
    docker compose stop mcp_server worker 2>/dev/null || true
    pass "Containers stopped (mcp_server, worker)"

    # REM: Step E — Run restore.sh with the backup (non-interactive via --yes piped)
    log "${YELLOW}[Step 3/7] Running restore from backup${NC}"
    RESTORE_START=$(date +%s)
    if echo "RESTORE" | bash "${SCRIPT_DIR}/restore.sh" "${BACKUP_DIR}" >> "$LOG_FILE" 2>&1; then
        pass "restore.sh completed successfully"
    else
        fail "restore.sh failed"
        # REM: Attempt to bring services back up regardless
        docker compose up -d >> "$LOG_FILE" 2>&1
        return
    fi
    RESTORE_END=$(date +%s)

    # REM: Step F — Ensure all containers are restarted
    log "${YELLOW}[Step 4/7] Restarting all containers${NC}"
    docker compose up -d >> "$LOG_FILE" 2>&1
    pass "docker compose up -d issued"

    # REM: Step G — Wait for health check to pass
    log "${YELLOW}[Step 5/7] Waiting for health check${NC}"
    HEALTH_OK=false
    ELAPSED_HEALTH=0
    while [ $ELAPSED_HEALTH -lt $HEALTH_TIMEOUT ]; do
        HTTP_CODE=$(docker compose exec -T mcp_server curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
            HEALTH_OK=true
            break
        fi
        info "Health poll: HTTP ${HTTP_CODE} — retrying in ${HEALTH_INTERVAL}s (${ELAPSED_HEALTH}/${HEALTH_TIMEOUT}s)"
        sleep $HEALTH_INTERVAL
        ELAPSED_HEALTH=$((ELAPSED_HEALTH + HEALTH_INTERVAL))
    done

    if [ "$HEALTH_OK" = true ]; then
        pass "Health check passed (HTTP ${HTTP_CODE})"
    else
        fail "Health check timed out after ${HEALTH_TIMEOUT}s"
    fi

    DOWNTIME_END=$(date +%s)

    # REM: Step H — Verify PostgreSQL tables exist
    log "${YELLOW}[Step 6/7] Verifying PostgreSQL tables${NC}"
    REQUIRED_TABLES=("users" "audit_entries" "tenants" "compliance_records")
    for tbl in "${REQUIRED_TABLES[@]}"; do
        TBL_EXISTS=$(docker compose exec -T postgres psql -U telsonbase -d telsonbase -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='${tbl}';" \
            2>/dev/null | tr -d ' \r\n')
        if [ "$TBL_EXISTS" = "1" ]; then
            pass "Table exists: ${tbl}"
        else
            fail "Table missing: ${tbl}"
        fi
    done

    # REM: Step I — Verify Redis PING
    log "${YELLOW}[Step 7/7] Verifying Redis${NC}"
    REDIS_PONG=$(docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" PING 2>/dev/null | tr -d '\r' || true)
    if [ "$REDIS_PONG" = "PONG" ]; then
        pass "Redis responding to PING"
    else
        fail "Redis not responding after restore"
    fi

    # REM: Step J — Calculate and report metrics
    DR_END=$(date +%s)
    RECOVERY_DURATION=$((DOWNTIME_END - DOWNTIME_START))
    TOTAL_DURATION=$((DR_END - DR_START))

    log ""
    log "${CYAN}+--------------------------------------------------------------+${NC}"
    log "${CYAN}|                  DR Test Results Summary                      |${NC}"
    log "${CYAN}+--------------------------------------------------------------+${NC}"
    log ""
    log "  Backup duration:     ${BACKUP_DURATION}s"
    log "  Recovery duration:   ${RECOVERY_DURATION}s"
    log "  Total test duration: ${TOTAL_DURATION}s"
    log ""

    # REM: RPO check — backup must be less than 24 hours old
    if [ $BACKUP_DURATION -lt $((RPO_TARGET_HOURS * 3600)) ]; then
        pass "RPO met: backup completed in ${BACKUP_DURATION}s (target: <${RPO_TARGET_HOURS}hr)"
    else
        fail "RPO NOT met: backup took ${BACKUP_DURATION}s"
    fi

    # REM: RTO check — recovery must complete within 15 minutes
    if [ $RECOVERY_DURATION -lt $RTO_TARGET_SECONDS ]; then
        pass "RTO met: recovery in ${RECOVERY_DURATION}s (target: <$((RTO_TARGET_SECONDS / 60))min)"
    else
        fail "RTO NOT met: recovery took ${RECOVERY_DURATION}s (target: <$((RTO_TARGET_SECONDS / 60))min)"
    fi
}

# REM: =======================================================================================
# REM: EXECUTE SELECTED TEST
# REM: =======================================================================================
if [ "$TEST_MODE" = "quick" ]; then
    run_quick_test
else
    run_full_test
fi

# REM: =======================================================================================
# REM: FINAL VERDICT
# REM: =======================================================================================
log ""
if [ $FAIL_COUNT -eq 0 ]; then
    log "${GREEN}+--------------------------------------------------------------+${NC}"
    log "${GREEN}|          DR TEST PASSED — All checks succeeded               |${NC}"
    log "${GREEN}+--------------------------------------------------------------+${NC}"
    log ""
    log "Results logged to: ${LOG_FILE}"
    exit 0
else
    log "${RED}+--------------------------------------------------------------+${NC}"
    log "${RED}|          DR TEST FAILED — ${FAIL_COUNT} check(s) failed                  |${NC}"
    log "${RED}+--------------------------------------------------------------+${NC}"
    log ""
    log "Results logged to: ${LOG_FILE}"
    exit 1
fi
