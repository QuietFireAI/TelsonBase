# TelsonBase Deployment Guide

**Version:** 9.0.0B
**Last Updated:** March 1, 2026
**Audience:** IT administrators, managed service providers (MSPs), and systems integrators deploying TelsonBase on customer premises for law firms and professional services organizations.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start](#2-quick-start)
3. [Detailed Installation](#3-detailed-installation)
4. [Post-Installation Checklist](#4-post-installation-checklist)
5. [Configuration Reference](#5-configuration-reference)
6. [Backup Configuration](#6-backup-configuration)
7. [Upgrading](#7-upgrading)
8. [Troubleshooting](#8-troubleshooting)
9. [Security Hardening](#9-security-hardening)
10. [Support](#10-support)

---

## 1. Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU cores | 4 | 8+ |
| RAM | 16 GB | 32 GB |
| Storage | 100 GB SSD | 500 GB NVMe SSD |
| Network | 100 Mbps | 1 Gbps |

**Storage breakdown (approximate):**
- Docker images: ~15 GB
- PostgreSQL data: 5-50 GB (scales with tenant count and audit history)
- Redis data: 1-4 GB
- Ollama models: 10-40 GB (depends on selected models)
- Backups: 20-100 GB (depends on retention policy)
- Logs: 5-20 GB

**Note:** Ollama (the local AI inference engine) is memory-intensive. For production workloads with concurrent users, 32 GB RAM is strongly recommended. GPU acceleration is optional but improves AI response times significantly.

### Operating System

| OS | Status |
|----|--------|
| Ubuntu 22.04 LTS | Recommended. All scripts and CI tested here. |
| Ubuntu 24.04 LTS | Supported. |
| Debian 12 | Supported. |
| Windows Server 2022 | Supported with Docker Desktop or WSL2. |
| Any Docker-capable Linux | Supported (RHEL 9, Rocky 9, etc.). |

### Software Dependencies

| Software | Minimum Version | Installation Reference |
|----------|----------------|----------------------|
| Docker Engine | 24.0+ | https://docs.docker.com/engine/install/ |
| Docker Compose | v2.20+ (plugin) | Included with Docker Engine 24+ |
| Git | 2.30+ | https://git-scm.com/downloads |
| curl | Any recent version | Pre-installed on most systems |
| openssl | 1.1+ | Pre-installed on most systems (used by generate_secrets.sh) |

Verify installed versions:

```bash
docker --version          # Docker version 24.x or higher
docker compose version    # Docker Compose version v2.x
git --version             # git version 2.x
```

### Network Requirements

| Requirement | Details |
|-------------|---------|
| Static IP | Required for production. Used by TLS certificate and DNS. |
| Domain name | Required for automatic TLS via Let's Encrypt. Optional if using self-signed certificates. |
| Port 80 (TCP) | HTTP -- automatically redirected to HTTPS by Traefik. |
| Port 443 (TCP) | HTTPS -- all production traffic. |
| Port 8000 (TCP) | MCP Server API (bound to localhost by default; exposed through Traefik in production). |
| Outbound HTTPS | Required for Let's Encrypt ACME challenge and optional external API integrations. |

**Internal ports (bound to 127.0.0.1, not exposed externally):**
- ~~5678: n8n workflow engine~~ — **removed**; Goose connects to port 8000 (`/mcp`)
- 9090: Prometheus metrics
- 3001: Grafana dashboards

**Firewall rules (inbound):**
```
ALLOW TCP 80   FROM 0.0.0.0/0    # HTTP (redirects to HTTPS)
ALLOW TCP 443  FROM 0.0.0.0/0    # HTTPS
DENY  ALL      FROM 0.0.0.0/0    # Default deny
```

---

## 2. Quick Start

For experienced administrators who want TelsonBase running in under 30 minutes.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/telsonbase.git
cd telsonbase

# 2. Configure environment
cp .env.example .env
# Edit .env — set TRAEFIK_ACME_EMAIL, TRAEFIK_DOMAIN, and TELSONBASE_ENV=production
# All secret values (API keys, passwords) are auto-populated in the next step.
nano .env

# 3. Generate secrets and bootstrap the stack
# This creates all cryptographic secrets, syncs them into .env,
# and generates the Mosquitto MQTT password file automatically.
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh

# 4. Build images and start all services
# --build is required on first deploy (no cached images exist yet)
docker compose up --build -d

# 5. Wait for services to initialize (60-90 seconds on first boot)
sleep 60

# 6. Run database migrations
docker compose exec mcp_server alembic upgrade head

# 7. Verify health
curl http://localhost:8000/health
```

After verification, proceed to [Section 3i](#3i-register-first-admin-user) to create the initial admin account.

---

## 3. Detailed Installation

### 3a. Clone the Repository

```bash
git clone https://github.com/your-org/telsonbase.git
cd telsonbase
```

Verify the directory structure includes:

```
telsonbase/
  docker-compose.yml
  Dockerfile
  .env.example
  scripts/
  monitoring/
  alembic/
  core/
  api/
```

### 3b. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set these three required values — everything else is auto-populated in the next step:

```bash
# Set to "production" for production deployments
TELSONBASE_ENV=production

# Your email for Let's Encrypt certificate notifications
TRAEFIK_ACME_EMAIL=admin@yourfirm.com

# The domain name pointing to this server's IP
TRAEFIK_DOMAIN=telsonbase.yourfirm.com
```

See [Section 5: Configuration Reference](#5-configuration-reference) for all available variables.

### 3c. Generate Secrets

Run the bootstrap script **after** creating `.env`. It generates all cryptographic secrets, syncs their values into `.env`, and creates the Mosquitto MQTT password file — no manual key copying required.

```bash
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh
```

This creates all files in `./secrets/` and auto-populates these `.env` values:

| Variable | Source |
|---|---|
| `MCP_API_KEY` | `secrets/telsonbase_mcp_api_key` |
| `JWT_SECRET_KEY` | `secrets/telsonbase_jwt_secret` |
| `POSTGRES_PASSWORD` | `secrets/telsonbase_postgres_password` |
| `REDIS_PASSWORD` | `secrets/telsonbase_redis_password` |
| `MOSQUITTO_PASSWORD` | `secrets/telsonbase_mqtt_password` |
| `WEBUI_SECRET_KEY` | `secrets/telsonbase_webui_secret` |
| `DATABASE_URL` | Updated inline with Postgres password |

It also regenerates `monitoring/mosquitto/password_file` using Docker — no separate `mosquitto` install required on the host.

**Important:** The `secrets/` directory is excluded from version control via `.gitignore`. Back up these files securely — if they are lost, all encrypted data becomes unrecoverable.

Verify secret generation:

```bash
./scripts/generate_secrets.sh --check
```

### 3d. Configure TLS

TelsonBase ships with Traefik as its reverse proxy, pre-configured for automatic TLS via Let's Encrypt.

**Option A: Automatic TLS with Let's Encrypt (recommended)**

1. Ensure your domain's DNS A record points to the server's public IP.
2. Ensure ports 80 and 443 are open and reachable from the internet.
3. Set `TRAEFIK_ACME_EMAIL` and `TRAEFIK_DOMAIN` in `.env`.
4. Start the stack. Traefik automatically obtains and renews certificates.

Certificates are stored in the `letsencrypt_data` Docker volume and persist across restarts.

**Option B: Self-signed certificates (air-gapped or internal networks)**

For environments without internet access or using internal CAs:

1. Generate a self-signed certificate:
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ./certs/telsonbase.key \
     -out ./certs/telsonbase.crt \
     -subj "/CN=telsonbase.local"
   ```

2. Mount the certificates in `docker-compose.yml` under the Traefik service:
   ```yaml
   volumes:
     - ./certs:/certs:ro
   ```

3. Add Traefik file provider configuration for the static certificate. Refer to Traefik documentation for details.

**TLS security features enabled by default:**
- HTTP-to-HTTPS redirect at the entrypoint level
- HSTS with 1-year max-age, includeSubdomains, and preload
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- XSS protection headers

### 3e. Start Services

```bash
# --build is required on first deploy to build the mcp_server/worker/beat images.
# Subsequent restarts can use `docker compose up -d` (cached layers).
docker compose up --build -d
```

This starts the following 12 services:

| # | Service | Image | Purpose |
|---|---------|-------|---------|
| 1 | traefik | traefik:v2.10 | TLS termination, reverse proxy, security headers |
| 2 | redis | redis:7-alpine | Session store, cache, audit chain, rate limiting |
| 3 | postgres | postgres:16-alpine | Durable storage (users, audit, tenants, compliance) |
| 4 | mailhog | mailhog/mailhog | Dev SMTP catcher — catches all outbound email (UI at port 8025). Remove in production and set real SMTP_* vars. |
| 5 | open-webui | ghcr.io/open-webui/open-webui | Human-AI interface |
| 6 | mosquitto | eclipse-mosquitto:2 | MQTT event bus for real-time agent communication |
| 7 | ollama | ollama/ollama | Local AI inference engine |
| 8 | mcp_server | (built from Dockerfile) | TelsonBase API server (FastAPI) |
| 9 | worker | (built from Dockerfile) | Celery background task workers |
| 10 | beat | (built from Dockerfile) | Celery scheduler (periodic tasks) |
| 11 | prometheus | prom/prometheus:v2.49.1 | Metrics collection |
| 12 | grafana | grafana/grafana:10.3.1 | Metrics dashboards and alerting |

Monitor startup progress:

```bash
# Watch all service logs
docker compose logs -f

# Check service status
docker compose ps
```

All services should show `Up` status with `(healthy)` within 60-90 seconds. Ollama may take longer on first boot while downloading models.

### 3f. Verify Health

```bash
# Check the MCP server health endpoint directly (works before TLS is configured)
curl -s http://localhost:8000/health | python3 -m json.tool

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "...",
#   "redis": "healthy",
#   "mqtt": "connected"
# }
```

In production with TLS configured and DNS pointing to the server:

```bash
curl -s https://your-domain.com/health | python3 -m json.tool
```

If using self-signed certificates:

```bash
curl -sk https://localhost/health
```

### 3g. Run Initial Database Migration

The PostgreSQL database must be initialized with the TelsonBase schema:

```bash
docker compose exec mcp_server alembic upgrade head
```

This creates 4 tables:
- `users` -- user accounts, hashed passwords, MFA configuration
- `audit_entries` -- cryptographic audit trail
- `tenants` -- multi-tenant isolation (client-matter scoping)
- `compliance_records` -- compliance tracking and legal hold records

Verify migration:

```bash
docker compose exec postgres psql -U telsonbase -c "\dt"
```

### 3h. Run Security Verification

Before registering users or going live, run the security battery to verify that all auth, rate limiting, input validation, and audit chain controls are functioning correctly on this deployment.

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py -q
```

Expected result:

```
93 passed in ~30s
```

If any tests fail, do not proceed. Review the failure output — it will point to the specific control that is misconfigured or broken. Common causes: missing environment variable, wrong secret file permissions, database migration not applied.

The security battery covers:
- Authentication gates (valid/invalid tokens, expired tokens, tampered tokens)
- Rate limiting (brute force protection, lockout enforcement)
- Input validation (injection attempts, malformed payloads, oversized inputs)
- CAPTCHA enforcement
- Audit chain integrity
- Trust tier enforcement
- MFA flow validation

**This step is mandatory before registering users or opening the system to clients.**

---

### 3i. Register First Admin User

The first user registered automatically receives the `super_admin` role:

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@yourfirm.com",
    "password": "YourSecurePassword123!"
  }'
```

Note: The first user does not require a CAPTCHA. Subsequent users must include a solved `captcha_challenge_id` from the `/v1/auth/captcha/generate` endpoint.

In production with TLS, replace `http://localhost:8000` with `https://your-domain.com`.

**Password requirements:**
- Minimum 12 characters
- Must contain uppercase, lowercase, numbers, and special characters

Store the returned user ID and authentication token securely.

### 3j. Enable MFA for Admin Account

Multi-factor authentication is mandatory for administrative accounts. Enroll immediately after registration:

```bash
curl -X POST https://your-domain.com/v1/security/mfa/enroll \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json"
```

This returns:
- A TOTP secret (for manual entry into an authenticator app)
- A QR code URI (for scanning with Google Authenticator, Authy, etc.)
- A set of backup codes (store these offline in a secure location)

Complete enrollment by confirming with a valid TOTP code:

```bash
curl -X POST https://your-domain.com/v1/security/mfa/confirm \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

### 3k. Verify Audit Chain

TelsonBase maintains a cryptographic audit chain (SHA-256 hash-linked) for tamper-evident logging. Verify its integrity:

```bash
curl -s https://your-domain.com/v1/audit/chain/verify \
  -H "Authorization: Bearer <your-token>"
```

Expected response:

```json
{
  "valid": true,
  "chain_length": 3,
  "message": "Audit chain integrity verified"
}
```

---

## 4. Post-Installation Checklist

Complete every item before declaring the deployment production-ready.

- [ ] All 12 Docker services running (`docker compose ps` shows all healthy)
- [ ] Health endpoint returns HTTP 200 (`curl https://your-domain.com/health`)
- [ ] PostgreSQL tables created (4 tables: users, audit_entries, tenants, compliance_records)
- [ ] Redis connected and persisting (`docker compose exec redis redis-cli PING` returns PONG)
- [ ] TLS certificate valid (`curl -v https://your-domain.com 2>&1 | grep "SSL certificate verify ok"`)
- [ ] HTTP-to-HTTPS redirect working (`curl -I http://your-domain.com` returns 301 to HTTPS)
- [ ] HSTS header present (`curl -sI https://your-domain.com | grep strict-transport-security`)
- [ ] Admin user created with `super_admin` role
- [ ] MFA enabled for admin account
- [ ] Backup cron job configured (see [Section 6](#6-backup-configuration))
- [ ] Audit chain verification passing
- [ ] Grafana dashboard accessible at `http://localhost:3001` (or via SSH tunnel)
- [ ] Prometheus collecting metrics at `http://localhost:9090`
- [ ] Firewall rules reviewed (only ports 80 and 443 exposed externally)
- [ ] `TELSONBASE_ENV=production` set in `.env`
- [ ] All placeholder values in `.env` replaced with real values
- [ ] `./secrets/` directory backed up to secure offline storage

---

## 5. Configuration Reference

All configuration is managed through the `.env` file and Docker secrets.

### Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `TELSONBASE_ENV` | `development` | Yes | Set to `production` for production deployments. Enforces strict secrets validation. |
| `MCP_API_KEY` | (none) | Yes* | API key for MCP server authentication. In production, read from Docker secret. |
| `JWT_SECRET_KEY` | (none) | Yes* | Secret key for JWT token signing. In production, read from Docker secret. |
| `JWT_EXPIRATION_HOURS` | `24` | No | JWT token lifetime in hours. |
| `TELSONBASE_ENCRYPTION_KEY` | (none) | Yes* | AES encryption key for data at rest. In production, read from Docker secret. |
| `TELSONBASE_ENCRYPTION_SALT` | (none) | Yes* | Salt for key derivation. In production, read from Docker secret. |
| `TRAEFIK_ACME_EMAIL` | (none) | Yes | Email for Let's Encrypt certificate notifications. |
| `TRAEFIK_DOMAIN` | (none) | Yes | Domain name for TLS certificate and Traefik routing. |
| `CORS_ORIGINS` | `[]` | No | JSON array of allowed CORS origins (e.g., `["https://app.example.com"]`). |
| `ALLOWED_EXTERNAL_DOMAINS` | See .env.example | No | JSON array of whitelisted external API domains. |
| `REDIS_PASSWORD` | `telsonbase_redis_dev` | Yes* | Redis authentication password. Set by generate_secrets.sh. |
| `POSTGRES_PASSWORD` | `telsonbase_dev` | Yes* | PostgreSQL password. Set by generate_secrets.sh. |
| `MOSQUITTO_PASSWORD` | `telsonbase_mqtt_dev` | Yes* | MQTT broker password. Set by generate_secrets.sh. |
| `BACKUP_DIR_HOST_PATH` | `./backups` | No | Host path for backup storage. |
| `LOG_LEVEL` | `INFO` | No | Logging verbosity: DEBUG, INFO, WARNING, ERROR. |
| `AUDIT_LOG_PATH` | `/app/logs/audit.log` | No | Path inside container for audit log files. |
| `WEBUI_SECRET_KEY` | (none) | No | Secret key for Open-WebUI sessions. |
| `GRAFANA_ADMIN_USER` | `admin` | No | Grafana administrator username. |
| `GRAFANA_ADMIN_PASSWORD` | (none) | Yes* | Grafana administrator password. Read from Docker secret. |

\* In production mode, these values are read from Docker secrets generated by `generate_secrets.sh`. You do not need to set them in `.env` if secrets files exist.

### Docker Secrets

| Secret File | Mount Path | Purpose |
|-------------|-----------|---------|
| `secrets/telsonbase_mcp_api_key` | `/run/secrets/telsonbase_mcp_api_key` | MCP API authentication key |
| `secrets/telsonbase_jwt_secret` | `/run/secrets/telsonbase_jwt_secret` | JWT signing secret |
| `secrets/telsonbase_encryption_key` | `/run/secrets/telsonbase_encryption_key` | Data encryption key |
| `secrets/telsonbase_encryption_salt` | `/run/secrets/telsonbase_encryption_salt` | Encryption key derivation salt |
| `secrets/telsonbase_grafana_password` | `/run/secrets/telsonbase_grafana_password` | Grafana admin password |

### Network Segmentation

TelsonBase uses 5 isolated Docker networks to prevent lateral movement:

| Network | Type | Connected Services |
|---------|------|--------------------|
| `frontend` | Bridge | Traefik, Open-WebUI, MCP Server (incl. `/mcp` gateway), Grafana |
| `backend` | Bridge | MCP Server, Worker, Beat, Traefik, Prometheus |
| `data` | Bridge (internal) | Redis, PostgreSQL, Mosquitto, MCP Server, Worker, Beat |
| `ai` | Bridge (internal) | Ollama, Open-WebUI, MCP Server, Worker |
| `monitoring` | Bridge (internal) | Prometheus, Grafana |

Networks marked `internal` have no external access. Services on the `data` and `ai` networks cannot be reached from outside the Docker environment.

---

## 6. Backup Configuration

TelsonBase includes built-in backup and disaster recovery tooling. See `docs/BACKUP_RECOVERY.md` for the full reference.

### Configure Daily Automated Backups

Add a cron job to run backups daily at 2:00 AM:

```bash
# Edit the crontab
crontab -e

# Add this line:
0 2 * * * /path/to/telsonbase/scripts/backup.sh >> /var/log/telsonbase-backup.log 2>&1
```

The backup script performs:
- PostgreSQL dump (`pg_dump`)
- Redis snapshot (`BGSAVE`)
- Secrets archive (encrypted)
- Configuration files

**Recovery Point Objective (RPO):** 24 hours (with daily backups).
**Recovery Time Objective (RTO):** 15 minutes.

### Verify Backup Integrity

Run the disaster recovery smoke test:

```bash
./scripts/dr_test.sh --quick
```

For a full DR cycle (backup, stop, restore, verify):

```bash
./scripts/dr_test.sh --full
```

See `docs/DISASTER_RECOVERY_TEST.md` for details on automated DR testing.

### Backup Retention

Recommended retention policy:
- Daily backups: 7 days
- Weekly backups: 4 weeks
- Monthly backups: 12 months

Implement retention by adding cleanup logic to your cron job or using a tool like `logrotate`.

### Offsite Backup

For compliance (HIPAA, CJIS), copy backups to an offsite location:

```bash
# Example: rsync to a remote server
rsync -az --delete /path/to/telsonbase/backups/ user@backup-server:/backups/telsonbase/
```

---

## 7. Upgrading

### Standard Upgrade Procedure

```bash
cd /path/to/telsonbase

# 1. Create a backup before upgrading
./scripts/backup.sh

# 2. Pull the latest code
git pull

# 3. Rebuild and restart services (zero-downtime for stateless services)
docker compose up -d --build

# 4. Run any new database migrations
docker compose exec mcp_server alembic upgrade head

# 5. Verify health
curl -s https://your-domain.com/health

# 6. Check all services are running
docker compose ps
```

### Rollback Procedure

If an upgrade causes issues:

```bash
# 1. Stop services
docker compose down

# 2. Revert to the previous version
git checkout <previous-tag-or-commit>

# 3. Restore from backup if database migrations were applied
./scripts/restore.sh /path/to/backup/telsonbase_YYYYMMDD_complete.tar

# 4. Restart services
docker compose up -d
```

### Version Compatibility

Database migrations are forward-only. Reverting to a previous application version after running migrations may require a database restore. Always back up before upgrading.

---

## 8. Troubleshooting

### Container Will Not Start

**Symptom:** `docker compose ps` shows a service as `restarting` or `exited`.

```bash
# Check the service logs
docker compose logs <service-name>

# Example:
docker compose logs mcp_server
```

**Common causes:**
- Missing or invalid `.env` values (check for leftover `CHANGE_ME` placeholders)
- Port conflict (another process using port 80, 443, or 8000)
- Missing secrets files (re-run `./scripts/generate_secrets.sh`)
- Insufficient memory (Ollama requires at least 4 GB)

### Redis Connection Refused

**Symptom:** MCP server logs show `ConnectionError: Error connecting to Redis`.

```bash
# Verify Redis is running
docker compose ps redis

# Test Redis connectivity
docker compose exec redis redis-cli -a <redis-password> PING

# Check Redis logs
docker compose logs redis
```

**Common causes:**
- `REDIS_PASSWORD` mismatch between `.env` and the running Redis instance
- Redis container not on the `data` network
- Resource limits exceeded (check `docker stats redis`)

**Fix:** If the password was changed after initial startup, the running Redis instance still uses the old password. Restart Redis:

```bash
docker compose restart redis
```

### PostgreSQL Authentication Failure

**Symptom:** `FATAL: password authentication failed for user "telsonbase"`.

```bash
# Check PostgreSQL logs
docker compose logs postgres

# Verify connection
docker compose exec postgres psql -U telsonbase -c "SELECT 1"
```

**Common causes:**
- `POSTGRES_PASSWORD` was changed in `.env` after the initial database creation. The PostgreSQL data volume retains the original password.

**Fix:** Either use the original password or recreate the volume (data loss warning):

```bash
# Option 1: Reset password inside PostgreSQL
docker compose exec postgres psql -U telsonbase -c "ALTER USER telsonbase PASSWORD 'new_password';"

# Option 2: Destroy and recreate (LOSES ALL DATA -- restore from backup after)
docker compose down
docker volume rm telsonbase_postgres_data
docker compose up -d
docker compose exec mcp_server alembic upgrade head
```

### TLS Certificate Errors

**Symptom:** Browser shows "Your connection is not private" or `curl` returns certificate errors.

```bash
# Check Traefik logs for ACME errors
docker compose logs traefik | grep -i "acme\|certificate\|error"
```

**Common causes:**
- DNS not pointing to the server's IP address
- Port 80 blocked (Let's Encrypt HTTP-01 challenge requires port 80)
- Rate limit exceeded on Let's Encrypt (5 certificates per domain per week)
- `TRAEFIK_DOMAIN` in `.env` does not match the DNS record

**Fix:**
1. Verify DNS resolution: `dig +short your-domain.com`
2. Verify port 80 is reachable: `curl http://your-domain.com` from an external host
3. Check Traefik ACME storage: `docker compose exec traefik cat /letsencrypt/acme.json`

### Migration Fails

**Symptom:** `alembic upgrade head` returns an error.

```bash
# Check current migration state
docker compose exec mcp_server alembic current

# Check migration history
docker compose exec mcp_server alembic history
```

**Common causes:**
- Database not reachable (PostgreSQL not running or wrong `DATABASE_URL`)
- Migration already applied (safe to ignore "already at head" messages)
- Schema conflict from manual database changes

### Service Dependency Failures

**Symptom:** MCP server starts but endpoints return 500 errors.

TelsonBase services have the following dependency chain:

```
traefik -> mcp_server -> redis, postgres, mosquitto, ollama
worker -> redis, postgres, mosquitto, ollama
beat -> redis
grafana -> prometheus
```

Check that all upstream dependencies are healthy:

```bash
docker compose ps --format "table {{.Service}}\t{{.Status}}"
```

### Viewing Logs

```bash
# All services
docker compose logs -f --tail 100

# Specific service
docker compose logs -f mcp_server

# Filter for errors
docker compose logs mcp_server 2>&1 | grep -i error
```

---

## 9. Security Hardening

Complete these steps after installation to achieve a production-hardened deployment.

### Verify Secrets Strength

```bash
./scripts/generate_secrets.sh --check
```

This validates that all secrets meet minimum entropy requirements and no default/placeholder values remain.

### Enable Encryption at Rest

TelsonBase supports volume-level encryption for all persistent data. See `docs/ENCRYPTION_AT_REST.md` for the complete guide.

**Linux (LUKS):**
```bash
# Encrypt the Docker data directory or individual volumes
cryptsetup luksFormat /dev/sdX
cryptsetup luksOpen /dev/sdX telsonbase-data
mkfs.ext4 /dev/mapper/telsonbase-data
```

**Windows Server (BitLocker):**
Enable BitLocker on the drive hosting Docker volumes.

### Review Firewall Rules

Verify that only ports 80 and 443 are exposed externally:

```bash
# Ubuntu/Debian
sudo ufw status verbose

# RHEL/Rocky
sudo firewall-cmd --list-all
```

Ensure the following ports are NOT exposed to the internet:
- 8000 (MCP server direct -- should only be accessed through Traefik)
- 8025 (MailHog -- dev email catcher, never expose in production)
- 9090 (Prometheus)
- 3001 (Grafana)
- 1883 (MQTT)

### Configure Log Rotation

Docker's built-in log rotation is already configured in `docker-compose.yml` (10 MB max, 3 files per service). For system-level log rotation of backup and audit logs:

```bash
# /etc/logrotate.d/telsonbase
/var/log/telsonbase-backup.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

### Disable Unused Services

If certain services are not needed, stop them to reduce the attack surface:

```bash
# Example: disable Open-WebUI if not using the chat interface
docker compose stop open-webui
```

### Account Security

- Enforce MFA for all user accounts, not just administrators.
- Review the account lockout policy: 5 failed attempts triggers a 15-minute lockout.
- Set `JWT_EXPIRATION_HOURS` to the minimum acceptable value (default: 24 hours).
- Configure HIPAA-compliant session timeouts via session management settings.

### Network Hardening

- Use a VPN or SSH tunnel for accessing internal services (Grafana, Prometheus).
- Consider placing the server behind a corporate firewall with IDS/IPS.
- TelsonBase's Docker network segmentation (5 isolated networks) prevents lateral movement between tiers.

### Regular Security Maintenance

| Task | Frequency |
|------|-----------|
| Rotate secrets (`generate_secrets.sh --rotate`) | Quarterly |
| Review audit chain integrity | Weekly |
| Update Docker images (`docker compose pull`) | Monthly |
| Run DR test (`dr_test.sh --quick`) | Monthly |
| Full DR test (`dr_test.sh --full`) | Quarterly |
| Review user accounts and permissions | Monthly |
| Update base OS and apply security patches | Monthly |

---

## 10. Support

### Documentation

| Document | Path | Description |
|----------|------|-------------|
| Backup & Recovery | `docs/BACKUP_RECOVERY.md` | Backup procedures, restore steps, RPO/RTO |
| Secrets Management | `docs/SECRETS_MANAGEMENT.md` | Secret generation, rotation, validation |
| Encryption at Rest | `docs/ENCRYPTION_AT_REST.md` | Volume encryption, compliance mapping |
| Disaster Recovery Test | `docs/DISASTER_RECOVERY_TEST.md` | Automated DR test procedures |
| HA Architecture | `docs/HA_ARCHITECTURE.md` | Scaling to Docker Swarm / Kubernetes |
| Security Architecture | `docs/SECURITY_ARCHITECTURE.md` | Zero-trust model, network segmentation |
| SOC 2 Type I | `docs/SOC2_TYPE_I.md` | 51 controls across 5 Trust Service Criteria |
| Compliance Roadmap | `docs/COMPLIANCE_ROADMAP.md` | HIPAA, HITRUST, CJIS, SOC 2 certification path |
| Troubleshooting | `docs/TROUBLESHOOTING.md` | Extended troubleshooting reference |
| API Reference | `docs/API_REFERENCE.md` | Endpoint documentation |

### Architecture Overview

```
                    Internet
                       |
                  [Firewall]
                       |
              +--------+--------+
              |    Traefik      |  (TLS, HSTS, security headers)
              |   :80 / :443   |
              +--------+--------+
                       |
              +--------+--------+
              |   MCP Server    |  (FastAPI, 140+ endpoints)
              |     :8000       |
              +--------+--------+
              /    |    |    \    \
         Redis  Postgres MQTT  Ollama  /mcp
          :6379  :5432  :1883  :11434  (Goose)
              \    |    |    /
              +--------+--------+
              |  Celery Workers |
              |   + Beat        |
              +-----------------+
                       |
              +--------+--------+
              | Prometheus      |
              |  + Grafana      |
              +-----------------+
```

### Contact

For deployment assistance, contact your TelsonBase account representative or visit [telsonbase.com](https://telsonbase.com).

---

*This document is part of the TelsonBase deployment package. Keep it updated when infrastructure changes are made.*
