# ClawCoat Backup & Recovery Guide

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

---

## Recovery Objectives

| Metric | Target | Description |
|--------|--------|-------------|
| **RPO** (Recovery Point Objective) | **24 hours** | Maximum acceptable data loss. Daily automated backups ensure no more than 24 hours of data is ever at risk. |
| **RTO** (Recovery Time Objective) | **15 minutes** | Maximum time to restore a fully operational instance from backup. Database size is the primary variable. |

---

## What Gets Backed Up

- **PostgreSQL** - Full SQL dump of the `telsonbase` database (schema + data)
- **Redis** - Point-in-time `dump.rdb` snapshot
- **Secrets** - Tarball of the `secrets/` directory (encryption keys, API keys, JWT secrets)
- **Configuration** - `.env`, `docker-compose.yml`, `alembic.ini`
- **Manifest** - `backup_manifest.txt` with file sizes for verification

---

## Automated Backup Setup (Recommended)

Add this cron entry to run backups daily at 2:00 AM:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your TelsonBase installation):
0 2 * * * cd /path/to/telsonbase && ./scripts/backup.sh >> /var/log/telsonbase-backup.log 2>&1
```

Backups older than 30 days are automatically deleted. Override with:

```bash
BACKUP_RETENTION_DAYS=60 ./scripts/backup.sh
```

---

## Manual Backup Procedure

```bash
cd /path/to/telsonbase
./scripts/backup.sh
```

The script will:
1. Verify PostgreSQL and Redis are running
2. Dump PostgreSQL to `postgres_backup.sql`
3. Trigger Redis BGSAVE and copy `dump.rdb`
4. Archive the `secrets/` directory
5. Copy configuration files
6. Verify all backup files and print a summary

Output directory: `backups/YYYYMMDD_HHMMSS/`

---

## Recovery Procedure

### Step 1: Identify the Backup

```bash
ls -la backups/
```

### Step 2: Run the Restore Script

```bash
./scripts/restore.sh backups/20260210_120000/
```

### Step 3: Confirm the Destructive Operation

The script will prompt you to type `RESTORE` to confirm.

### Step 4: Automatic Recovery Sequence

The script performs these steps automatically:
1. Stops `mcp_server`, `worker`, and `beat` services
2. Drops and recreates the PostgreSQL database, imports the SQL dump
3. Stops Redis, replaces `dump.rdb`, restarts Redis
4. Extracts secrets (current secrets are preserved as `secrets.pre-restore.*`)
5. Restores configuration files (originals preserved as `*.pre-restore.*`)
6. Runs `docker compose up -d` and performs health checks

### Step 5: Post-Restore Verification

- Check the application: `http://localhost:8000/`
- Review logs: `docker compose logs --tail=50`
- Clean up pre-restore backups when satisfied:
  ```bash
  rm -rf secrets.pre-restore.*
  rm -f *.pre-restore.*
  ```

---

## Offsite Backup (Operator Responsibility)

The backup script stores backups locally in `backups/`. **You must copy these offsite.**

Recommended offsite targets:
- Drobo NAS (local network)
- AWS S3 / Snowball device
- Any remote storage with encryption at rest

Example rsync to NAS:

```bash
rsync -av backups/ nas:/volume1/telsonbase-backups/
```

---

## Shared Responsibility Model

| Responsibility | Owner |
|---------------|-------|
| Backup script correctness | TelsonBase project (automated) |
| Running backups on schedule | **Operator** |
| Offsite backup storage | **Operator** |
| Monitoring backup success/failure | **Operator** |
| Executing restore when needed | **Operator** |
| Testing restore procedure periodically | **Operator** |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pg_dump` fails | Ensure PostgreSQL container is running: `docker compose ps` |
| Redis dump is empty | Normal for fresh instances with no data; not a failure |
| Restore exceeds 15-min RTO | Consider pruning old data or upgrading hardware |
| Services fail after restore | Check `docker compose logs`; secrets mismatch may require re-running `generate_secrets.sh` |

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
