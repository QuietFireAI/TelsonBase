# TelsonBase Disaster Recovery Test Procedure

**Version:** v11.0.1 · **Maintainer:** Quietfire AI
**Last Updated:** March 8, 2026
**Script:** `scripts/dr_test.sh`

---

## 1. Purpose

This document describes the automated disaster recovery (DR) test procedure for TelsonBase. The DR test validates that backup and restore scripts function correctly and that recovery time objectives are achievable under realistic conditions.

**Recommended frequency:**
- Quarterly (minimum) as part of compliance obligations
- After any major infrastructure change (database migration, Docker version upgrade, new services)
- After changes to `backup.sh` or `restore.sh`
- Before any production deployment to a new client environment

---

## 2. Prerequisites

Before running the DR test, confirm the following:

- Docker Engine is running and `docker compose` is functional
- All TelsonBase services are up (`docker compose ps` shows healthy containers)
- At least one valid backup exists in `backups/` (for `--quick` mode)
- No active client sessions or in-flight transactions (for `--full` mode)
- Sufficient disk space for a new backup (check with `df -h`)
- The scripts are executable: `chmod +x scripts/dr_test.sh scripts/backup.sh scripts/restore.sh`

---

## 3. Running the Tests

### Quick Smoke Test (< 5 minutes)

Validates readiness without performing destructive operations:

```bash
./scripts/dr_test.sh --quick
```

**What it checks:**
1. A valid backup exists in the `backups/` directory
2. `restore.sh` is executable
3. PostgreSQL accepts connections
4. Redis responds to PING
5. Core Docker services (postgres, redis, mcp_server) are running

### Full DR Cycle Test (5-15 minutes)

Performs a complete backup-stop-restore-verify cycle:

```bash
./scripts/dr_test.sh --full
```

**What it does:**
1. Creates a fresh backup via `backup.sh`
2. Stops the `mcp_server` and `worker` containers (simulated outage)
3. Restores from the backup just created via `restore.sh`
4. Restarts all containers
5. Polls the health endpoint until responsive (timeout: 5 minutes)
6. Verifies PostgreSQL tables: `users`, `audit_entries`, `tenants`, `compliance_records`
7. Verifies Redis connectivity
8. Calculates backup duration, recovery duration, and total downtime
9. Evaluates RPO and RTO against targets

**IMPORTANT:** The full test causes temporary service downtime. Schedule during a maintenance window.

---

## 4. RPO and RTO Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **RPO** (Recovery Point Objective) | < 24 hours | Time since last backup; met if daily backups run via cron |
| **RTO** (Recovery Time Objective) | < 15 minutes | Wall-clock time from outage start to health check pass |

---

## 5. Pass Criteria

The DR test passes (exit code 0) when ALL of the following are true:

- Backup completes without errors
- Restore completes without errors
- Health endpoint responds with HTTP 200, 401, or 403 within 5 minutes
- All four required PostgreSQL tables exist after restore
- Redis responds to PING after restore
- Recovery duration is under 15 minutes (RTO target)

---

## 6. Sample Output

```
+--------------------------------------------------------------+
|       TelsonBase -- Disaster Recovery Test (full)            |
|                    by Quietfire AI                              |
+--------------------------------------------------------------+

[Step 1/7] Creating fresh backup
  [PASS] backup.sh completed successfully
  [INFO] Backup duration: 12s
[Step 2/7] Simulating outage -- stopping mcp_server and worker
  [PASS] Containers stopped (mcp_server, worker)
[Step 3/7] Running restore from backup
  [PASS] restore.sh completed successfully
[Step 4/7] Restarting all containers
  [PASS] docker compose up -d issued
[Step 5/7] Waiting for health check
  [PASS] Health check passed (HTTP 200)
[Step 6/7] Verifying PostgreSQL tables
  [PASS] Table exists: users
  [PASS] Table exists: audit_entries
  [PASS] Table exists: tenants
  [PASS] Table exists: compliance_records
[Step 7/7] Verifying Redis
  [PASS] Redis responding to PING

  Backup duration:     12s
  Recovery duration:   87s
  Total test duration: 104s

  [PASS] RPO met: backup completed in 12s (target: <24hr)
  [PASS] RTO met: recovery in 87s (target: <15min)

+--------------------------------------------------------------+
|          DR TEST PASSED -- All checks succeeded               |
+--------------------------------------------------------------+
```

---

## 7. Remediation Steps if Tests Fail

| Failure | Likely Cause | Remediation |
|---------|-------------|-------------|
| No valid backup found | Backup cron not configured or backups purged | Run `./scripts/backup.sh` manually; configure cron per `backup.sh` header |
| restore.sh not executable | Permissions lost during git clone or file copy | `chmod +x scripts/restore.sh scripts/backup.sh` |
| PostgreSQL not responding | Container crashed or misconfigured | `docker compose logs postgres`; check `.env` for `POSTGRES_PASSWORD` |
| Redis not responding | Container crashed or password mismatch | `docker compose logs redis`; verify `REDIS_PASSWORD` in `.env` |
| Health check timed out | Application startup failure or dependency issue | `docker compose logs mcp_server`; check for import errors or missing env vars |
| Table missing after restore | Backup was taken from empty database or schema mismatch | Run `alembic upgrade head` after restore; verify backup was non-empty |
| RTO exceeded (>15min) | Large database, slow disk I/O, or resource constraints | Profile with `time ./scripts/restore.sh`; consider faster storage or parallel restore |
| backup.sh failed | Disk full, Docker not running, or container not healthy | Check `df -h`; verify `docker compose ps` shows healthy services |

---

## 8. Compliance Relevance

This DR test procedure satisfies evidence requirements for the following controls:

- **SOC 2 A1.2** - Recovery testing: "The entity tests recovery plan procedures supporting system recovery to meet its objectives." This script provides automated, logged, and timestamped evidence of recovery testing.

- **HIPAA 164.308(a)(7)(ii)(D)** - Testing and revision procedures: "Implement procedures for periodic testing and revision of contingency plans." The quarterly execution schedule and logged results fulfill this requirement.

- **HITRUST 12.e** - Testing of information security continuity: evidence of tested backup and restore procedures.

Test results are written to `logs/dr_test_YYYYMMDD.log` and should be retained for audit purposes (minimum 7 years for HIPAA, 1 year for SOC 2).

---

## 9. Related Documents

- [Backup and Recovery](BACKUP_RECOVERY.md) - Backup script usage and cron setup
- [Disaster Recovery Plan](DISASTER_RECOVERY.md) - Full DR plan and recovery scenarios
- [Encryption at Rest](ENCRYPTION_AT_REST.md) - Data protection at the volume level
- [Incident Response](INCIDENT_RESPONSE.md) - Procedures when a real disaster occurs

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
