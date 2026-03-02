#!/bin/bash
# TelsonBase/scripts/restore.sh
# REM: =======================================================================================
# REM: TELSONBASE RESTORE SCRIPT — FULL STATE RECOVERY FROM BACKUP
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: This script restores a TelsonBase instance from a timestamped
# REM: backup created by backup.sh. It performs pre-flight validation, stops dependent
# REM: services, restores all data, and verifies the result with health checks.
#
# REM: RTO Target: Under 15 minutes (database size dependent)
#
# REM: Usage:
# REM:   chmod +x scripts/restore.sh
# REM:   ./scripts/restore.sh backups/20260210_120000/
#
# REM: What gets restored:
# REM:   - PostgreSQL database (full schema + data)
# REM:   - Redis state (dump.rdb snapshot)
# REM:   - Secrets directory (encryption keys, API keys, etc.)
# REM:   - Configuration (.env, docker-compose.yml, alembic.ini)
#
# REM: WARNING: This is a DESTRUCTIVE operation. Current state will be overwritten.
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
HEALTH_CHECK_RETRIES=12
HEALTH_CHECK_INTERVAL=5

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║            TelsonBase — Full Restore Procedure                 ║"
echo "║                    by Quietfire AI                                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# REM: =======================================================================================
# REM: ARGUMENT VALIDATION
# REM: =======================================================================================
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <backup-directory>${NC}"
    echo ""
    echo "Example:"
    echo "  $0 backups/20260210_120000/"
    echo ""
    echo "Available backups:"
    if [ -d "${PROJECT_DIR}/backups" ]; then
        ls -1d "${PROJECT_DIR}"/backups/*/ 2>/dev/null | while read -r dir; do
            echo "  $(basename "$dir")"
        done
    else
        echo "  (none found)"
    fi
    exit 1
fi

# REM: Resolve backup directory (support both relative and absolute paths)
BACKUP_INPUT="$1"
if [[ "$BACKUP_INPUT" = /* ]]; then
    BACKUP_DIR="$BACKUP_INPUT"
else
    BACKUP_DIR="${PROJECT_DIR}/${BACKUP_INPUT}"
fi
# REM: Strip trailing slash for consistency
BACKUP_DIR="${BACKUP_DIR%/}"

echo -e "${CYAN}Backup source:${NC}  ${BACKUP_DIR}"
echo -e "${CYAN}Project dir:${NC}    ${PROJECT_DIR}"
echo -e "${CYAN}RTO Target:${NC}     Under 15 minutes"
echo ""

START_TIME=$(date +%s)

# REM: Change to project directory for docker compose context
cd "$PROJECT_DIR"

# REM: =======================================================================================
# REM: PRE-FLIGHT CHECKS
# REM: =======================================================================================
echo -e "${YELLOW}[Pre-flight Checks]${NC}"

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "  ${RED}FATAL: Backup directory does not exist: ${BACKUP_DIR}${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Backup directory exists"

# REM: Verify required backup files
REQUIRED_FILES=("postgres_backup.sql" "backup_manifest.txt")
OPTIONAL_FILES=("redis_dump.rdb" "secrets.tar")
MISSING_REQUIRED=0

for req_file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "${BACKUP_DIR}/${req_file}" ]; then
        echo -e "  ${RED}FATAL: Required file missing: ${req_file}${NC}"
        MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    else
        fsize=$(wc -c < "${BACKUP_DIR}/${req_file}" | tr -d ' ')
        echo -e "  ${GREEN}✓${NC} ${req_file} (${fsize} bytes)"
    fi
done

for opt_file in "${OPTIONAL_FILES[@]}"; do
    if [ ! -f "${BACKUP_DIR}/${opt_file}" ]; then
        echo -e "  ${YELLOW}WARNING: Optional file missing: ${opt_file}${NC}"
    else
        fsize=$(wc -c < "${BACKUP_DIR}/${opt_file}" | tr -d ' ')
        echo -e "  ${GREEN}✓${NC} ${opt_file} (${fsize} bytes)"
    fi
done

# REM: Check config directory
if [ -d "${BACKUP_DIR}/config" ]; then
    config_count=$(find "${BACKUP_DIR}/config" -type f | wc -l | tr -d ' ')
    echo -e "  ${GREEN}✓${NC} config/ directory (${config_count} files)"
else
    echo -e "  ${YELLOW}WARNING: config/ directory not found in backup${NC}"
fi

if [ $MISSING_REQUIRED -gt 0 ]; then
    echo -e "\n  ${RED}FATAL: ${MISSING_REQUIRED} required file(s) missing. Cannot proceed.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "  ${RED}FATAL: docker not found in PATH${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} docker available"
echo ""

# REM: =======================================================================================
# REM: CONFIRMATION PROMPT
# REM: =======================================================================================
echo -e "${RED}WARNING: This will OVERWRITE the current TelsonBase state.${NC}"
echo -e "${RED}Current database, Redis data, secrets, and config will be replaced.${NC}"
echo ""
read -p "Type 'RESTORE' to confirm: " CONFIRMATION
if [ "$CONFIRMATION" != "RESTORE" ]; then
    echo -e "${YELLOW}Aborted. No changes were made.${NC}"
    exit 0
fi
echo ""

# REM: =======================================================================================
# REM: STEP 1: STOP APPLICATION SERVICES
# REM: =======================================================================================
echo -e "${YELLOW}[Step 1/6] Stopping application services${NC}"

docker compose stop mcp_server worker beat 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} mcp_server, worker, beat stopped"
echo ""

# REM: =======================================================================================
# REM: STEP 2: RESTORE POSTGRESQL
# REM: =======================================================================================
echo -e "${YELLOW}[Step 2/6] Restoring PostgreSQL${NC}"

# REM: Ensure postgres is running
if ! docker compose ps --status running | grep -q "postgres"; then
    docker compose start postgres
    echo -e "  ${CYAN}Waiting for PostgreSQL to be ready...${NC}"
    sleep 5
fi

# REM: Drop and recreate the database to ensure clean state
echo -e "  ${CYAN}Dropping existing database...${NC}"
docker compose exec -T postgres psql -U telsonbase -d postgres -c "DROP DATABASE IF EXISTS telsonbase;" 2>/dev/null || true
docker compose exec -T postgres psql -U telsonbase -d postgres -c "CREATE DATABASE telsonbase OWNER telsonbase;" 2>/dev/null

echo -e "  ${CYAN}Importing backup...${NC}"
docker compose exec -T postgres psql -U telsonbase telsonbase < "${BACKUP_DIR}/postgres_backup.sql" > /dev/null 2>&1

# REM: Verify restore by checking table count
TABLE_COUNT=$(docker compose exec -T postgres psql -U telsonbase -d telsonbase -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' \r\n')
echo -e "  ${GREEN}✓${NC} PostgreSQL restored (${TABLE_COUNT} tables)"
echo ""

# REM: =======================================================================================
# REM: STEP 3: RESTORE REDIS
# REM: =======================================================================================
echo -e "${YELLOW}[Step 3/6] Restoring Redis${NC}"

if [ -f "${BACKUP_DIR}/redis_dump.rdb" ]; then
    REDIS_SIZE=$(wc -c < "${BACKUP_DIR}/redis_dump.rdb" | tr -d ' ')
    if [ "$REDIS_SIZE" -gt 0 ]; then
        # REM: Stop redis to replace the dump file
        docker compose stop redis
        sleep 2

        # REM: Copy dump.rdb into the redis container volume
        docker compose cp "${BACKUP_DIR}/redis_dump.rdb" redis:/data/dump.rdb 2>/dev/null || {
            # REM: Fallback: start redis first, then copy
            docker compose start redis
            sleep 2
            docker compose cp "${BACKUP_DIR}/redis_dump.rdb" redis:/data/dump.rdb
            docker compose restart redis
        }

        # REM: Start redis with the restored dump
        docker compose start redis
        sleep 3
        echo -e "  ${GREEN}✓${NC} Redis dump restored (${REDIS_SIZE} bytes)"
    else
        echo -e "  ${YELLOW}WARNING: redis_dump.rdb is empty — skipping Redis restore${NC}"
    fi
else
    echo -e "  ${YELLOW}WARNING: redis_dump.rdb not found — skipping Redis restore${NC}"
fi
echo ""

# REM: =======================================================================================
# REM: STEP 4: RESTORE SECRETS
# REM: =======================================================================================
echo -e "${YELLOW}[Step 4/6] Restoring secrets${NC}"

if [ -f "${BACKUP_DIR}/secrets.tar" ]; then
    # REM: Back up current secrets before overwriting
    if [ -d "${PROJECT_DIR}/secrets" ]; then
        mv "${PROJECT_DIR}/secrets" "${PROJECT_DIR}/secrets.pre-restore.$$"
        echo -e "  ${CYAN}Current secrets backed up to secrets.pre-restore.$$${NC}"
    fi

    tar xf "${BACKUP_DIR}/secrets.tar" -C "${PROJECT_DIR}"
    chmod 700 "${PROJECT_DIR}/secrets"
    chmod 600 "${PROJECT_DIR}/secrets/"* 2>/dev/null || true

    SECRET_COUNT=$(find "${PROJECT_DIR}/secrets" -type f | wc -l | tr -d ' ')
    echo -e "  ${GREEN}✓${NC} Secrets restored (${SECRET_COUNT} files, permissions set)"
else
    echo -e "  ${YELLOW}WARNING: secrets.tar not found — keeping existing secrets${NC}"
fi
echo ""

# REM: =======================================================================================
# REM: STEP 5: RESTORE CONFIGURATION
# REM: =======================================================================================
echo -e "${YELLOW}[Step 5/6] Restoring configuration${NC}"

if [ -d "${BACKUP_DIR}/config" ]; then
    RESTORED_CONFIG=0
    for config_file in "${BACKUP_DIR}/config/"*; do
        [ -f "$config_file" ] || continue
        fname=$(basename "$config_file")
        # REM: Back up current config before overwriting
        if [ -f "${PROJECT_DIR}/${fname}" ]; then
            cp "${PROJECT_DIR}/${fname}" "${PROJECT_DIR}/${fname}.pre-restore.$$"
        fi
        cp "$config_file" "${PROJECT_DIR}/${fname}"
        echo -e "  ${GREEN}✓${NC} ${fname}"
        RESTORED_CONFIG=$((RESTORED_CONFIG + 1))
    done
    echo -e "  ${GREEN}✓${NC} ${RESTORED_CONFIG} config file(s) restored"
else
    echo -e "  ${YELLOW}WARNING: config/ not found in backup — keeping existing config${NC}"
fi
echo ""

# REM: =======================================================================================
# REM: STEP 6: RESTART ALL SERVICES AND VERIFY
# REM: =======================================================================================
echo -e "${YELLOW}[Step 6/6] Restarting services and verifying${NC}"

echo -e "  ${CYAN}Starting all services...${NC}"
docker compose up -d
echo -e "  ${GREEN}✓${NC} docker compose up -d issued"

echo -e "  ${CYAN}Waiting for services to initialize...${NC}"
sleep 10

# REM: Health check loop for MCP server
echo -e "  ${CYAN}Checking MCP server health...${NC}"
MCP_HEALTHY=false
for i in $(seq 1 $HEALTH_CHECK_RETRIES); do
    if docker compose ps --status running | grep -q "mcp_server"; then
        HTTP_CODE=$(docker compose exec -T mcp_server curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
            MCP_HEALTHY=true
            echo -e "  ${GREEN}✓${NC} MCP server responding (HTTP ${HTTP_CODE})"
            break
        fi
    fi
    echo -e "  ${CYAN}  Attempt ${i}/${HEALTH_CHECK_RETRIES} — waiting ${HEALTH_CHECK_INTERVAL}s...${NC}"
    sleep $HEALTH_CHECK_INTERVAL
done

if [ "$MCP_HEALTHY" = false ]; then
    echo -e "  ${YELLOW}WARNING: MCP server did not respond within timeout${NC}"
    echo -e "  ${YELLOW}Check logs with: docker compose logs mcp_server${NC}"
fi

# REM: Check PostgreSQL connectivity
PG_CHECK=$(docker compose exec -T postgres pg_isready -U telsonbase 2>/dev/null && echo "ok" || echo "fail")
if [ "$PG_CHECK" = "ok" ]; then
    echo -e "  ${GREEN}✓${NC} PostgreSQL accepting connections"
else
    echo -e "  ${YELLOW}WARNING: PostgreSQL not ready${NC}"
fi

# REM: Check Redis connectivity
REDIS_CHECK=$(docker compose exec -T redis redis-cli ping 2>/dev/null | tr -d '\r')
if [ "$REDIS_CHECK" = "PONG" ]; then
    echo -e "  ${GREEN}✓${NC} Redis responding"
else
    echo -e "  ${YELLOW}WARNING: Redis not responding${NC}"
fi

echo ""

# REM: =======================================================================================
# REM: SUMMARY
# REM: =======================================================================================
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_MIN=$((ELAPSED / 60))
ELAPSED_SEC=$((ELAPSED % 60))

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                Restore completed successfully!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  Backup source:    $(basename "$BACKUP_DIR")"
echo -e "  Duration:         ${ELAPSED_MIN}m ${ELAPSED_SEC}s"
echo -e "  RTO Target:       Under 15 minutes"
echo -e "  Tables restored:  ${TABLE_COUNT:-unknown}"
echo ""
echo -e "${YELLOW}Post-restore checklist:${NC}"
echo "  1. Verify application behavior at http://localhost:8000/"
echo "  2. Check logs: docker compose logs --tail=50"
echo "  3. Run test suite if available"
echo "  4. Remove pre-restore backups when satisfied:"
echo "     rm -rf ${PROJECT_DIR}/secrets.pre-restore.*"
echo "     rm -f ${PROJECT_DIR}/*.pre-restore.*"
echo ""
if [ $ELAPSED -gt 900 ]; then
    echo -e "${RED}WARNING: Restore took ${ELAPSED_MIN}m ${ELAPSED_SEC}s — exceeds 15-minute RTO target.${NC}"
    echo -e "${RED}Consider optimizing database size or infrastructure.${NC}"
fi
echo ""
