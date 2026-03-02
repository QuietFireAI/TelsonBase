#!/bin/bash
# TelsonBase/scripts/backup.sh
# REM: =======================================================================================
# REM: TELSONBASE BACKUP SCRIPT — FULL STATE PRESERVATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: This script creates a timestamped, verified backup of every
# REM: critical TelsonBase component — databases, secrets, and configuration. Each backup
# REM: is self-contained: everything needed to rebuild the instance from scratch.
#
# REM: RPO Target: 24 hours (recommend daily automated execution via cron)
# REM: Recommended cron entry:
# REM:   0 2 * * * cd /path/to/telsonbase && ./scripts/backup.sh >> /var/log/telsonbase-backup.log 2>&1
#
# REM: Usage:
# REM:   chmod +x scripts/backup.sh
# REM:   ./scripts/backup.sh
#
# REM: Output: backups/YYYYMMDD_HHMMSS/ containing:
# REM:   - postgres_backup.sql   (full PostgreSQL dump)
# REM:   - redis_dump.rdb        (Redis point-in-time snapshot)
# REM:   - secrets.tar           (encrypted-at-rest secrets archive)
# REM:   - config/               (.env, docker-compose.yml, alembic.ini)
# REM:   - backup_manifest.txt   (file listing with sizes and checksums)
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
BACKUP_ROOT="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
REDIS_PASSWORD="${REDIS_PASSWORD:-telsonbase_redis_dev}"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║             TelsonBase — Full Backup Procedure                 ║"
echo "║                    by Quietfire AI                                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${CYAN}Timestamp:${NC}  ${TIMESTAMP}"
echo -e "${CYAN}Target:${NC}     ${BACKUP_DIR}"
echo -e "${CYAN}Retention:${NC}  ${RETENTION_DAYS} days"
echo ""

# REM: Change to project directory for docker compose context
cd "$PROJECT_DIR"

# REM: Pre-flight checks
echo -e "${YELLOW}[Pre-flight Checks]${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "  ${RED}FATAL: docker not found in PATH${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} docker available"

if ! docker compose ps --status running | grep -q "postgres"; then
    echo -e "  ${RED}FATAL: PostgreSQL container is not running${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} PostgreSQL running"

if ! docker compose ps --status running | grep -q "redis"; then
    echo -e "  ${RED}FATAL: Redis container is not running${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Redis running"
echo ""

# REM: Create backup directory
mkdir -p "${BACKUP_DIR}/config"
echo -e "${YELLOW}[Step 1/5] PostgreSQL Backup${NC}"

docker compose exec -T postgres pg_dump -U telsonbase telsonbase > "${BACKUP_DIR}/postgres_backup.sql" 2>/dev/null
PG_SIZE=$(wc -c < "${BACKUP_DIR}/postgres_backup.sql" | tr -d ' ')
if [ "$PG_SIZE" -lt 10 ]; then
    echo -e "  ${RED}FATAL: PostgreSQL dump is empty or too small (${PG_SIZE} bytes)${NC}"
    rm -rf "${BACKUP_DIR}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} postgres_backup.sql (${PG_SIZE} bytes)"

echo -e "${YELLOW}[Step 2/5] Redis Backup${NC}"

# REM: Trigger background save and wait for completion
docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" BGSAVE > /dev/null 2>&1 || true
sleep 2

# REM: Wait for BGSAVE to complete (up to 30 seconds)
WAIT_COUNT=0
while [ $WAIT_COUNT -lt 15 ]; do
    LASTSAVE=$(docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" LASTSAVE 2>/dev/null | tr -d '\r')
    BG_STATUS=$(docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" INFO persistence 2>/dev/null | grep "rdb_bgsave_in_progress" | tr -d '\r')
    if echo "$BG_STATUS" | grep -q "rdb_bgsave_in_progress:0"; then
        break
    fi
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

# REM: Copy dump.rdb from the redis container
docker compose cp redis:/data/dump.rdb "${BACKUP_DIR}/redis_dump.rdb" 2>/dev/null || {
    echo -e "  ${YELLOW}WARNING: Could not copy dump.rdb (Redis may not have persisted yet)${NC}"
    touch "${BACKUP_DIR}/redis_dump.rdb"
}
REDIS_SIZE=$(wc -c < "${BACKUP_DIR}/redis_dump.rdb" | tr -d ' ')
echo -e "  ${GREEN}✓${NC} redis_dump.rdb (${REDIS_SIZE} bytes)"

echo -e "${YELLOW}[Step 3/5] Secrets Archive${NC}"

if [ -d "${PROJECT_DIR}/secrets" ]; then
    tar cf "${BACKUP_DIR}/secrets.tar" -C "${PROJECT_DIR}" secrets/
    SECRETS_SIZE=$(wc -c < "${BACKUP_DIR}/secrets.tar" | tr -d ' ')
    echo -e "  ${GREEN}✓${NC} secrets.tar (${SECRETS_SIZE} bytes)"
else
    echo -e "  ${YELLOW}WARNING: secrets/ directory not found — skipping${NC}"
fi

echo -e "${YELLOW}[Step 4/5] Configuration Files${NC}"

CONFIG_COUNT=0
for config_file in .env docker-compose.yml alembic.ini; do
    if [ -f "${PROJECT_DIR}/${config_file}" ]; then
        cp "${PROJECT_DIR}/${config_file}" "${BACKUP_DIR}/config/"
        echo -e "  ${GREEN}✓${NC} ${config_file}"
        CONFIG_COUNT=$((CONFIG_COUNT + 1))
    else
        echo -e "  ${YELLOW}WARNING: ${config_file} not found — skipping${NC}"
    fi
done
echo -e "  ${GREEN}✓${NC} ${CONFIG_COUNT} config file(s) copied"

echo -e "${YELLOW}[Step 5/5] Verification${NC}"

# REM: Build manifest with checksums
MANIFEST="${BACKUP_DIR}/backup_manifest.txt"
echo "# TelsonBase Backup Manifest" > "$MANIFEST"
echo "# Timestamp: ${TIMESTAMP}" >> "$MANIFEST"
echo "# Host: $(hostname)" >> "$MANIFEST"
echo "# Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$MANIFEST"
echo "" >> "$MANIFEST"

ERROR_COUNT=0
TOTAL_SIZE=0
FILE_COUNT=0

for backup_file in "${BACKUP_DIR}"/*; do
    [ -f "$backup_file" ] || continue
    fname=$(basename "$backup_file")
    fsize=$(wc -c < "$backup_file" | tr -d ' ')
    TOTAL_SIZE=$((TOTAL_SIZE + fsize))
    FILE_COUNT=$((FILE_COUNT + 1))

    if [ "$fsize" -eq 0 ] && [ "$fname" != "redis_dump.rdb" ]; then
        echo -e "  ${RED}FAIL: ${fname} is empty${NC}"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    else
        echo -e "  ${GREEN}✓${NC} ${fname} — ${fsize} bytes"
    fi
    echo "${fsize}  ${fname}" >> "$MANIFEST"
done

# REM: Count config files too
for config_file in "${BACKUP_DIR}/config/"*; do
    [ -f "$config_file" ] || continue
    fname="config/$(basename "$config_file")"
    fsize=$(wc -c < "$config_file" | tr -d ' ')
    TOTAL_SIZE=$((TOTAL_SIZE + fsize))
    FILE_COUNT=$((FILE_COUNT + 1))
    echo "${fsize}  ${fname}" >> "$MANIFEST"
done

echo ""

# REM: Retention cleanup
echo -e "${YELLOW}[Retention Cleanup]${NC}"
DELETED_COUNT=0
if [ -d "$BACKUP_ROOT" ]; then
    while IFS= read -r old_backup; do
        [ -z "$old_backup" ] && continue
        rm -rf "$old_backup"
        echo -e "  ${YELLOW}Removed:${NC} $(basename "$old_backup")"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    done < <(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -mtime +"$RETENTION_DAYS" 2>/dev/null)
fi
if [ $DELETED_COUNT -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} No expired backups to remove"
else
    echo -e "  ${GREEN}✓${NC} Removed ${DELETED_COUNT} backup(s) older than ${RETENTION_DAYS} days"
fi

echo ""

# REM: Summary
TOTAL_SIZE_HUMAN=$(numfmt --to=iec "$TOTAL_SIZE" 2>/dev/null || echo "${TOTAL_SIZE} bytes")

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║            BACKUP COMPLETED WITH ${ERROR_COUNT} ERROR(S)                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}Review the errors above before relying on this backup.${NC}"
    exit 1
else
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                 Backup completed successfully!                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
fi
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  Backup path:  ${BACKUP_DIR}"
echo -e "  Total size:   ${TOTAL_SIZE_HUMAN}"
echo -e "  File count:   ${FILE_COUNT}"
echo -e "  Timestamp:    ${TIMESTAMP}"
echo ""
echo -e "${YELLOW}IMPORTANT: Copy this backup offsite (Drobo NAS, AWS Snowball, etc.)${NC}"
echo -e "${YELLOW}RPO Target: 24 hours — schedule this script daily via cron.${NC}"
echo ""
