# TelsonBase — AWS Live Testing Guide

**Version:** 9.0.0B
**Date:** March 1, 2026
**Purpose:** Validate the complete TelsonBase stack on real cloud infrastructure

---

## Why AWS (and Why Briefly)

You need to prove TelsonBase works on hardware that isn't your local machine. AWS gives you compute-on-demand for hours, not months. The goal: spin up, test everything, collect evidence, terminate. Total cost under $5.

This is not a deployment. It's a validation session.

---

## Instance Selection

| Option | Instance | Specs | $/hour | 4hr Cost | Best For |
|--------|----------|-------|--------|----------|----------|
| **Recommended** | `g4dn.xlarge` | 4 vCPU, 16GB RAM, 1x NVIDIA T4 (16GB VRAM) | $0.53 | ~$2.12 | Full stack + GPU inference (gemma2:9b, llama3:8b) |
| CPU-only | `r6i.xlarge` | 4 vCPU, 32GB RAM | $0.25 | ~$1.00 | CPU Ollama inference (slower but functional) |
| Budget | `t3.xlarge` | 4 vCPU, 16GB RAM | $0.17 | ~$0.68 | Stack verification only (phi3:mini, small models) |

**OS:** Ubuntu 24.04 LTS AMI (Docker installs cleanly, matches your compose stack)

**Storage:** 50GB gp3 EBS ($0.08/GB/month = $4/month, but you'll have it for hours, pennies)

**Region:** us-east-1 (cheapest, most availability)

### What's New in v9.0.0B

Nothing on the AWS side — pricing is stable. What changed is your stack:

- **709 tests** (up from 509) — OpenClaw governance (54 tests), Identiclaw DID auth, real estate agents (transaction/compliance/doc prep), Manners compliance framework, schemathesis hardening, contract tripwires, adversarial CAPTCHA tests, and stability fixes all added coverage.
- **Multi-stage Dockerfile** — build tools (gcc, binutils) now in a builder stage only. Runtime image is clean: eliminates 13 LOW binutils CVEs from the image. Gateway has the same pattern.
- **ecdsa removed post-install** — CVE-2024-23342 HIGH. python-jose transitive dep, unused (TelsonBase uses HS256 only). Safe to remove.
- **wheel 0.46.2 enforced** in both Dockerfiles — CVE-2026-24049 HIGH was wheel <=0.46.1. Fixed.
- **apt-get upgrade -y** in runtime stage — patches gnutls28 and tar MEDIUM CVEs at build time.
- **Startup fixes** — Celery beat crash loop fixed (depends_on: service_healthy + --pidfile/--schedule flags). Traefik ACME moved to `docker-compose.prod.yml` overlay (no constant ACME errors in base stack). Grafana duplicate UID provisioning fixed.
- **docker-compose.prod.yml** — Production TLS overlay. For AWS testing, use base `docker-compose.yml` only. ACME/HTTPS requires a real domain.
- **Secrets fully automated** — `generate_secrets.sh` now auto-syncs all secrets into `.env` and generates the mosquitto password file via Docker. Zero manual key copying.
- **Secret file permissions** — All secrets generated as 644 (was 600). Containers can now read their secrets without root. No manual `chmod` step needed.
- **mosquitto MOSQUITTO_PASSWORD env var** — docker-compose.yml now passes the env var to the mosquitto container so its health check uses the real generated password.
- **open-webui healthcheck** — Changed from `wget` (not in image) to `curl -sf`. Reliable health detection.
- **5 isolated Docker networks** — compose file is heavier; validate it builds cleanly on fresh hardware.
- **OpenClaw governance verified on DigitalOcean** — Full 8-step pipeline live-tested March 1, 2026. All governance tiers (quarantine → probation), kill switch, and audit chain confirmed.

---

## Provisioning Steps

### 1. Launch Instance

```
AWS Console → EC2 → Launch Instance
├── Name: telsonbase-test
├── AMI: Ubuntu Server 24.04 LTS (HVM, SSD Volume Type)
├── Instance type: g4dn.xlarge (or your chosen option)
├── Key pair: Create new → download .pem file → guard it
├── Network: Default VPC
├── Security Group: 
│   ├── SSH (port 22) from YOUR IP only
│   ├── HTTP (port 8000) from YOUR IP only (API)
│   ├── Custom TCP (port 3000) from YOUR IP only (Open-WebUI)
│   ├── Custom TCP (port 9090) from YOUR IP only (Prometheus)
│   ├── Custom TCP (port 3001) from YOUR IP only (Grafana)
│   └── DO NOT open 0.0.0.0/0 for anything
├── Storage: 50 GB gp3
│   └── ☑ Delete on Termination (CRITICAL — check this box)
└── Launch
```

### 2. Create a Fresh Tarball (run this on your local Windows machine FIRST)

Before connecting to AWS, package your current codebase. Run this from Git Bash or
Windows Terminal (PowerShell) in the TelsonBase project directory:

```bash
# From Git Bash — run this BEFORE SSHing into AWS
# Navigate to your project root first:
cd /c/claude_code/Telsonbase

# Create a clean tarball (excludes secrets, backups, __pycache__, .git)
tar --exclude='.git' \
    --exclude='./secrets' \
    --exclude='./backups' \
    --exclude='./__pycache__' \
    --exclude='./.env' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='./monitoring/mosquitto/password_file' \
    -czf backups/telsonbase_v9.0.0B_aws_test_$(date +%Y%m%d).tar.gz .

# Verify it was created and has a reasonable size (should be 5-20 MB)
ls -lh backups/telsonbase_v9.0.0B_aws_test_*.tar.gz
```

Note the exact filename — you'll need it in the next step.

### 3. Connect and Setup

```bash
# SSH in (run from Git Bash or Windows Terminal, same directory as your .pem file)
ssh -i your-key.pem ubuntu@<public-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# Verify Docker Compose is available (comes bundled with Docker now)
docker compose version  # Should show v2.x

# In a SEPARATE terminal on your local machine — upload your tarball
# (replace the filename with the one you just created above)
scp -i your-key.pem \
  /c/claude_code/Telsonbase/backups/telsonbase_v9.0.0B_aws_test_YYYYMMDD.tar.gz \
  ubuntu@<public-ip>:~/

# Back on the EC2 instance — extract and enter the project
mkdir telsonbase
tar -xzf telsonbase_v9.0.0B_aws_test_*.tar.gz -C telsonbase/
cd telsonbase/
```

### 4. Configure and Launch

```bash
# Step 1 — Configure environment FIRST (generate_secrets.sh syncs into .env, so .env must exist)
cp .env.example .env
nano .env
# Three values to change for AWS testing:
#   TELSONBASE_ENV=staging       (not production — skips strict TLS/SSL requirements)
#   TRAEFIK_ACME_EMAIL=your@email.com
#   TRAEFIK_DOMAIN=<public-ip>   (just the IP — no domain needed for staging)
# Leave everything else. generate_secrets.sh fills in all keys automatically.

# Step 2 — Generate cryptographic secrets (auto-syncs all keys into .env)
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh
# On fresh instance: runs straight through, no prompts
# Generates secrets/, creates monitoring/mosquitto/password_file, syncs all keys into .env

# Step 3 — Build and launch (first build takes 5-10 minutes — compiling Python packages)
docker compose up --build -d

# Watch it come up — wait until ALL services show "healthy" (not "starting")
docker compose ps
# If anything shows "starting" or "unhealthy" after 2 minutes, check logs:
docker compose logs <service_name>

# REQUIRED: Run database migrations — creates all PostgreSQL tables
# Do this ONCE after first launch. Without it, the API will return 500 errors.
docker compose exec mcp_server alembic upgrade head
# Expected output: "Running upgrade  -> 001...", "002...", "003..." — all applied
```

---

## Test Phases

### Phase 1 — Does It Breathe? (15 minutes)

```bash
# All services healthy?
docker compose ps

# API responds?
curl http://localhost:8000/

# Swagger docs load?
curl -s http://localhost:8000/docs | head -20

# System status (with auth)?
curl -H "X-API-Key: $(cat secrets/telsonbase_mcp_api_key)" http://localhost:8000/v1/system/status

# Open-WebUI?
curl -s http://localhost:3000 | head -5

# MailHog (dev email catcher)?
curl -s http://localhost:8025 | head -5

# Prometheus?
curl http://localhost:9090/-/healthy

# Grafana?
curl http://localhost:3001/api/health

# No ERROR lines in startup?
docker compose logs --tail=50 mcp_server | grep -i error
```

**Stop here if anything fails.** Everything else depends on these.

### Phase 2 — Auth and Security Gates (30 minutes)

```bash
# Get your API key
API_KEY=$(cat secrets/telsonbase_mcp_api_key)

# Every /v1/ endpoint WITHOUT auth should return 401/403
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/system/status
# Expected: 401 or 403

# Get a JWT token (api_key goes in the JSON body, not the header)
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$API_KEY\"}"
# Expected: 200 with access_token

# Save the token
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$API_KEY\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use JWT on subsequent requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/system/status
# Expected: 200

# Garbage JWT — should be rejected
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer garbage_token_12345" \
  http://localhost:8000/v1/system/status
# Expected: 401

# Rate limiting — hit an endpoint 70 times fast (burst threshold is 60)
for i in $(seq 1 70); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-API-Key: $API_KEY" \
    http://localhost:8000/v1/system/status
done
# Expected: 200s for first ~60, then 429s after burst threshold

# Check audit log — every auth event should be logged (logs go to stdout via pythonjsonlogger)
docker compose logs mcp_server --tail=50 | grep -i "audit\|auth"
```

### Phase 3 — Ollama Live Integration (45 minutes)

This is the main event. First time real models run against your secured API.

```bash
# Health check — Ollama reachable?
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/llm/health

# Recommended models list
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/llm/models/recommended

# Pull a small model (watch worker logs in a second terminal)
curl -X POST http://localhost:8000/v1/llm/models/pull \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "phi3:mini"}'

# In another terminal, watch the pull progress:
docker compose logs -f worker

# Verify model landed
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/llm/models

# Generate — the moment of truth
curl -X POST http://localhost:8000/v1/llm/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is data sovereignty and why does it matter?", "model": "phi3:mini"}'

# Chat with context
curl -X POST http://localhost:8000/v1/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is TelsonBase?"}, {"role": "assistant", "content": "TelsonBase is a zero-trust AI agent security platform."}, {"role": "user", "content": "What makes it different from cloud AI?"}], "model": "phi3:mini"}'

# If on g4dn.xlarge with GPU — pull a bigger model
curl -X POST http://localhost:8000/v1/llm/models/pull \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma2:9b"}'

# Check audit — every pull, generate, chat should be logged (logs go to stdout)
docker compose logs mcp_server --tail=100 | grep -i "llm\|model\|generate"
```

### Phase 4 — Agent Capability Enforcement (30 minutes)

```bash
# What agents and capabilities are registered?
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/agents/

# Approval gates — try operations that require approval
# (model deletion, config changes should trigger approval flow)
# Check if approval request gets created:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/approvals/
```

### Phase 5 — Backup and Restore Fire Drill (45 minutes)

```bash
# System has been running 30+ minutes — there's real data now

# Trigger manual backup
docker compose exec worker celery -A celery_app.worker call \
  agents.backup_agent.tasks.perform_automated_backup \
  --args='["deployment"]'

# Wait for completion
docker compose logs -f worker  # Look for "backup task completed"

# Verify backup files exist and aren't empty
ls -lh backups/deployment_snapshots/
# Files should be >0 bytes, dated today

# THE HARD PART — actual restore test
# REM: n8n removed (disabled in v8.0.0). Use open_webui_data — safe non-critical volume.
docker compose down
docker volume rm telsonbase_open_webui_data  # open-webui: safe to wipe, will reprovision
docker volume create telsonbase_open_webui_data

# Restore from backup (replace filename with actual)
docker run --rm \
  -v ./backups:/backups_host \
  -v telsonbase_open_webui_data:/restore_target \
  alpine \
  tar -xzf /backups_host/deployment_snapshots/open_webui_data_backup_XXXXXXXX_XXXXXX.tar.gz -C /restore_target

# Bring it back up
docker compose up -d

# Did Open-WebUI come back? Check at http://<public-ip>:3000
```

### Phase 6 — Observability Validation (15 minutes)

```bash
# Prometheus scraping targets
curl http://localhost:9090/api/v1/targets | python3 -m json.tool | grep health

# Application metrics exposed?
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/metrics | head -30

# Grafana dashboard loads?
# Open http://<public-ip>:3001 in browser
# Login: admin / <password from secrets/telsonbase_grafana_password>
# TelsonBase Infrastructure dashboard should be auto-provisioned
```

### Phase 7 — Endpoint Stress Test (30 minutes)

```bash
# Install hey (HTTP load generator)
wget https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64
chmod +x hey_linux_amd64

# 50 requests, 10 concurrent to health endpoint
./hey_linux_amd64 -n 50 -c 10 \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/system/status

# 20 concurrent generate requests (will stress Ollama)
./hey_linux_amd64 -n 20 -c 5 \
  -H "Authorization: Bearer $TOKEN" \
  -m POST -T "application/json" \
  -d '{"prompt":"hello","model":"phi3:mini"}' \
  http://localhost:8000/v1/llm/generate

# Watch for OOM kills during stress
docker stats --no-stream
```

### Phase 8 — Federation Surface (15 minutes)

```bash
# Instance identity
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/federation/identity

# Create trust invitation
curl -X POST http://localhost:8000/v1/federation/invitations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trust_level": "standard", "expires_in_hours": 24}'

# List trust relationships
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/federation/relationships
```

### Phase 9 — Run Full Test Suite (20 minutes)

```bash
# Run pytest inside the container (excludes MQTT stress test — 26 tests, run separately)
docker compose exec mcp_server python -m pytest tests/ \
  --ignore=tests/test_mqtt_stress.py \
  -v --tb=short
# Expected: 701 passed, 1 skipped (702 collected)

# Run E2E tests separately — these hit real live endpoints, full stack must be healthy
docker compose exec mcp_server python -m pytest tests/test_e2e_integration.py \
  -v --tb=short -m e2e
# Expected: 22 passed

# Run security battery + OpenClaw + Identiclaw specifically
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py tests/test_openclaw.py tests/test_identiclaw.py \
  -v --tb=short
# Expected: 197 passed (93 security battery + 54 OpenClaw + 50 Identiclaw)
```

### Phase 10 — Collect Evidence (15 minutes)

Screenshot or save output for each:

- [ ] `docker compose ps` — all services healthy
- [ ] Full pytest output — 701 passed, 1 skipped (excludes 26 MQTT stress tests)
- [ ] Successful generate response with real model output
- [ ] 401 rejection on unauthenticated request
- [ ] 429 rate limit response
- [ ] Audit log sample showing hash chain entries
- [ ] Backup file listing with sizes
- [ ] `docker stats --no-stream` showing resource usage
- [ ] Prometheus targets page showing all scrapers active
- [ ] Grafana dashboard screenshot
- [ ] pip-audit output — 0 CVEs. Run: `docker compose exec mcp_server sh -c "pip install pip-audit -q && pip-audit -r /app/requirements.txt"`
- [ ] Docker Scout output — no Python CVEs (golang/Ubuntu = Ollama vendor, not yours)

---

## Cost Control Checklist

### Where AWS Charges Accumulate (The Traps)

| Trap | How It Gets You | Prevention |
|------|----------------|------------|
| EBS volumes | Don't auto-delete on instance termination by default | ☑ Check "Delete on Termination" at launch |
| EBS snapshots | Persist and bill at $0.05/GB/month | Don't create any. If you do, delete immediately after. |
| Elastic IPs | $0.005/hour if allocated but not attached to running instance | Don't allocate one. Use the auto-assigned public IP. |
| Stopped instances | EBS still bills even when instance is stopped | TERMINATE, don't stop. |
| Container registry (ECR) | Storage charges if you push images | Build from tarball on-instance. Don't push to ECR. |
| S3 | Easy to accidentally create buckets | Don't touch S3. You don't need it. |
| CloudWatch | Detailed monitoring costs extra | Don't enable detailed monitoring. |

### After Testing — Mandatory Cleanup

```bash
# 1. TERMINATE the instance (not stop — TERMINATE)
#    EC2 → Instances → Select → Instance State → Terminate

# 2. Delete orphaned EBS volumes
#    EC2 → Volumes → Delete any with State "available"

# 3. Release Elastic IPs (if you allocated one)
#    EC2 → Elastic IPs → Release

# 4. Delete snapshots (if you created any)
#    EC2 → Snapshots → Delete

# 5. Check next day
#    Billing Dashboard → verify $0 ongoing charges
```

### Expected Total Cost

| Scenario | Instance | Duration | Compute | Storage | Total |
|----------|----------|----------|---------|---------|-------|
| Full test (GPU) | g4dn.xlarge | 4 hours | $2.12 | ~$0.02 | ~$2.15 |
| Full test (CPU) | r6i.xlarge | 4 hours | $1.00 | ~$0.02 | ~$1.02 |
| Quick validation | t3.xlarge | 2 hours | $0.34 | ~$0.01 | ~$0.35 |

Data transfer out (under 100GB/month) is free tier. Data transfer in (uploading your tarball) is always free.

---

## Timeline

| When | What | Duration |
|------|------|----------|
| Day 1 | AWS live validation (this guide) | 4-5 hours |
| Day 2 | Compile evidence, screenshots, test output | 1-2 hours |
| Day 3+ | GitHub release / external review | Per schedule |

---

## What This Proves

Screenshots showing 709+ tests passing on fresh AWS hardware (709 total including MQTT stress excluded), a working generate endpoint with a real local model, audit logs with hash chains, 0 Python CVEs, and a Grafana dashboard with live metrics — that's not a concept. That's a system.

That's the difference between "I have an idea" and "I built it and it works."
