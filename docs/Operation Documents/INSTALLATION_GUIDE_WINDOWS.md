# ClawCoat - Installation Guide for Windows

**Version:** v11.0.1 · **Maintainer:** Quietfire AI
**Target Audience:** Windows users, including those new to Docker

---

## Before You Start

TelsonBase runs entirely in Docker. You do not install Python, Redis, or any other dependency directly on Windows - Docker handles all of that. What you need on your machine:

1. Docker Desktop
2. Git (for cloning the repo and running the setup script)

Both are covered in Prerequisites below.

---

## Prerequisites

### 1. Install Docker Desktop for Windows

**Download:** https://www.docker.com/products/docker-desktop/

**System requirements:**
- Windows 10 64-bit: Build 19041 or later (Pro, Enterprise, or Education)
- Windows 11 64-bit: any edition including Home
- 8 GB RAM minimum - Ollama (local LLM) needs headroom
- WSL 2 backend (recommended - Docker will prompt you to enable it)

**Steps:**
1. Run the installer - it may ask for administrator privileges
2. Follow the wizard and restart when prompted
3. Open Docker Desktop from the Start menu after restart
4. Wait for the whale icon in the system tray to show **"Docker Desktop is running"** before proceeding

**Verify:**
```powershell
docker --version
docker compose version
```

> TelsonBase uses `docker compose` (V2, built into Docker Desktop). The older `docker-compose` (with hyphen) is not needed.

---

### 2. Install Git for Windows

Git is required. The installer also includes **Git Bash**, which you will use to run the secrets setup script.

**Download:** https://git-scm.com/download/win

Or via winget:
```powershell
winget install Git.Git
```

Accept the defaults during installation. When it finishes, you will have both `git` (available in PowerShell and Command Prompt) and **Git Bash** (a separate app in your Start menu).

---

## Installation

### Clone the Repository

Open PowerShell, Command Prompt, or Git Bash:

```bash
git clone https://github.com/QuietFireAI/ClawCoat.git
cd TelsonBase
```

> Note the capital T - the directory is `TelsonBase`, not `telsonbase`.

---

## Configuration

This is the step most people skip past too quickly. Do not skip it.

### Step 1 - Copy the environment file

**In Git Bash or PowerShell:**
```bash
cp .env.example .env
```

**Or in Command Prompt:**
```cmd
copy .env.example .env
```

### Step 2 - Generate all secrets

Open **Git Bash** (from the Start menu - not PowerShell) and run:

```bash
bash scripts/generate_secrets.sh
```

This script does three things:
- Generates cryptographically random keys for the API, JWT, encryption, and all service passwords
- Writes them into the `secrets/` directory as Docker secret files
- Updates your `.env` file with the matching values

**Do not skip this step and do not generate keys manually.** TelsonBase uses Docker Secrets - keys must be in `secrets/` as files, not just in `.env`. The script handles both.

After the script completes, verify the secrets directory was created:

```bash
ls secrets/
```

You should see files including `telsonbase_mcp_api_key`. That file's contents are your API key - keep it.

```bash
cat secrets/telsonbase_mcp_api_key
```

### Step 3 - Enable the governance pipeline

**This step is required** to use agent governance features (trust levels, kill switch, Manners compliance, approval gates). Run this command before starting TelsonBase.

**In Git Bash:**
```bash
sed -i 's/OPENCLAW_ENABLED=false/OPENCLAW_ENABLED=true/' .env
```

**In PowerShell:**
```powershell
(Get-Content .env) -replace 'OPENCLAW_ENABLED=false', 'OPENCLAW_ENABLED=true' | Set-Content .env
```

Verify it took effect:

**Git Bash:**
```bash
grep OPENCLAW_ENABLED .env
```

**PowerShell:**
```powershell
Select-String -Path .env -Pattern "OPENCLAW_ENABLED"
```

Expected output: `OPENCLAW_ENABLED=true`

---

## Starting TelsonBase

### Step 1 - Confirm Docker Desktop is running

Check the system tray for the whale icon showing "Docker Desktop is running" before proceeding.

### Step 2 - Start all services

```bash
docker compose up -d --build
```

The first run downloads and builds images. This takes several minutes depending on your connection. Subsequent starts are fast.

### Step 3 - Run the database migration

**This step is required.** Without it, the API returns 500 errors on every request.

```bash
docker compose exec mcp_server alembic upgrade head
```

You will see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial schema
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add trust levels
```

This is a one-time step. You do not need to repeat it on subsequent restarts.

### Step 4 - Verify startup

```bash
docker compose ps
```

All 11 services should show **Up** or **healthy** (MailHog is dev-profile only - it won't appear here):

```
NAME                        STATUS
telsonbase-traefik-1        Up
telsonbase-redis-1          Up (healthy)
telsonbase-postgres-1       Up (healthy)
telsonbase-mcp_server-1     Up (healthy)
telsonbase-worker-1         Up
telsonbase-beat-1           Up
telsonbase-ollama-1         Up
telsonbase-open-webui-1     Up
telsonbase-mosquitto-1      Up
telsonbase-prometheus-1     Up
telsonbase-grafana-1        Up
```

If any service shows **Restarting**, check its logs:
```bash
docker compose logs mcp_server
```

### Step 5 - Check the health endpoint

```bash
curl http://localhost:8000/health
```

If `curl` is not available in your shell, use PowerShell:
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -ExpandProperty Content
```

Or open a browser to: `http://localhost:8000/health`

Expected response:
```json
{"status": "healthy", "version": "11.0.1"}
```

### Step 6 - Pull the AI model

TelsonBase uses Ollama for local LLM inference. Pull the default model after startup:

```bash
docker exec telsonbase-ollama-1 ollama pull gemma2:9b
```

This is a one-time download (~5.4 GB). The model is stored in the `ollama_data` Docker volume and persists across restarts.

Verify:
```bash
curl http://localhost:11434/api/tags
```

---

## Accessing TelsonBase

| Service | URL | What it is |
|---|---|---|
| **Admin Console** | http://localhost:8000/dashboard | Full governance dashboard |
| **User Console** | http://localhost:8000/console | Operator-focused view |
| **API Docs** | http://localhost:8000/docs | Interactive API reference (Swagger) |
| **Health Check** | http://localhost:8000/health | System status |
| **MCP Gateway** | http://localhost:8000/mcp | Connection point for Goose / Claude Desktop |
| **Open WebUI** | http://localhost:3000 | Chat interface for local LLM |
| **Grafana** | http://localhost:3001 | Infrastructure metrics |

### First login to the Admin Console

1. Open `http://localhost:8000/dashboard`
2. Click **Offline** in the header to open the connection panel
3. Enter your API key - find it with:
   ```bash
   cat secrets/telsonbase_mcp_api_key
   ```
4. Click **Connect** - the header will switch to **Live** and show the system health dot

**You're in.** From here, head to: `docs/Operation%20Documents/DASHBOARD_agent_registration.md` for the step-by-step walkthrough to register your first agent, promote it from QUARANTINE, and verify the governance loop.

---

## What to Know Before Your Agents Go Live

Two systems govern agent behavior at runtime. Neither is optional when `OPENCLAW_ENABLED=true`. Understanding them before you register your first agent will save you a lot of confusion.

### Trust Levels

Every agent starts at **QUARANTINE**. This is a hard default - not a misconfiguration. An agent at QUARANTINE is severely restricted and requires an operator to manually promote it before it can do useful work.

Promotion is done via the Admin Console (OpenClaw tab) or the API:

```bash
curl -X POST http://localhost:8000/v1/openclaw/{instance_id}/promote \
  -H "X-API-Key: $(cat secrets/telsonbase_mcp_api_key)" \
  -d '{"reason": "Initial deployment, reviewed and approved"}'
```

The five trust levels, in order:

| Level | What the agent can do |
|---|---|
| QUARANTINE | Severely restricted. Manual review required to proceed. |
| PROBATION | Limited capabilities. Closely monitored. |
| RESIDENT | Standard capabilities. Periodic re-verification. |
| CITIZEN | Full capabilities. 95%+ success rate required to maintain. |
| AGENT | Apex. 99.9% success rate, zero anomaly tolerance, re-verified every 3 days. |

Promotion is sequential - an agent cannot skip from QUARANTINE to CITIZEN. Demotion can skip levels instantly.

### Manners Scoring

Every agent receives a **Manners compliance score** from 0.0 to 1.0. The score is computed across five behavioral principles (human control, transparency, value alignment, privacy, security). It updates in real time as the agent acts.

| Score | Status | What it means operationally |
|---|---|---|
| 0.90-1.00 | EXEMPLARY | Full autonomous operation |
| 0.75-0.89 | COMPLIANT | Normal operation |
| 0.50-0.74 | DEGRADED | Increased monitoring, weekly review triggered |
| 0.25-0.49 | NON_COMPLIANT | Read-only access only |
| 0.00-0.24 | SUSPENDED | Quarantined, human review required |

**Two triggers for automatic quarantine:**
1. Score drops to SUSPENDED range (below 0.25)
2. Three or more violations within any 24-hour window - regardless of overall score

**One thing that catches new operators:** agents under 24 hours old are capped at DEGRADED status even with a perfect score. This is intentional - the system needs behavioral data before granting higher autonomy. Do not try to override it on day one.

**Where to see scores:** Admin Console → OpenClaw tab → agent card shows the current status badge. API: `GET /v1/manners/agent/{name}` for the full report.

**Common violations and their score impact:**

| Violation | Severity | What triggers it |
|---|---|---|
| APPROVAL_BYPASS | 0.30 | Action requiring approval attempted without one |
| CAPABILITY_VIOLATION | 0.25 | Access to resource outside declared capabilities |
| CROSS_TENANT_ACCESS | 0.35 | Data from another tenant accessed |
| UNSIGNED_MESSAGE | 0.15 | Inter-agent message sent without signature |
| NON_QMS_MESSAGE | 0.05 | Message to Foreman not in QMS format |

Violations decay over time - full weight for 24 hours, 50% at 72 hours, 25% at 168 hours. An agent that stops misbehaving recovers.

For the full scoring model, violation types, and API reference: `docs/Compliance Documents/MANNERS_COMPLIANCE.md`

---

## Running the Test Suite

720 tests covering what actually matters for a governance platform:

| Domain | Count | What it covers |
|---|---|---|
| Security battery | 96 | Auth, signing, key hashing, injection prevention, encryption, RBAC |
| QMS protocol | 115 | Message format, nonce replay, chain integrity, signature verification |
| Tool governance | 129 | Capability enforcement, egress control, approval gates |
| OpenClaw | 55 | Trust tier transitions, kill switch, Manners score updates |
| End-to-end | 29 | Full agent lifecycle from registration to suspension |
| Contracts | 7 | Enum stability - if you add a TenantType or TrustLevel, these fail fast |
| Core + other | 289 | Multi-tenancy isolation, federation, audit trail, CAPTCHA, HITL |

Run the full suite from inside the Docker container:

```bash
docker compose exec mcp_server python -m pytest tests/ -v
```

Expected result: **720 passed, 1 skipped, 0 failed**

The 1 skip is expected - it is an Alembic idempotency test that requires a live database in a specific state. Everything else should be green.

Run only the security battery:
```bash
docker compose exec mcp_server python -m pytest tests/security/ -v
```

Run a specific test file:
```bash
docker compose exec mcp_server python -m pytest tests/test_auth.py -v
```

Every test has a corresponding proof sheet in `proof_sheets/individual/`. Each sheet contains the exact pytest command to run it in isolation.

---

## Common Windows Issues

### "Docker daemon is not running"

Open Docker Desktop from the Start menu and wait for the whale icon in the system tray to show **"Docker Desktop is running"**. Then retry.

### WSL 2 not installed or incomplete

Open PowerShell as Administrator and run:
```powershell
wsl --install
```
Restart your computer. Reopen Docker Desktop.

### Hyper-V is not enabled

1. Open **Turn Windows features on or off** (search in Start menu)
2. Enable **Hyper-V** and **Windows Hypervisor Platform**
3. Restart

### "Port already in use"

```powershell
# Find what is using port 8000
netstat -ano | findstr :8000

# Kill it (replace 1234 with the PID from the output above)
taskkill /PID 1234 /F
```

Alternatively, switch TelsonBase to port 8001 instead. Run this in **Git Bash** from the TelsonBase directory:

```bash
sed -i 's/"8000:8000"/"8001:8000"/' docker-compose.yml
```

Then access TelsonBase at `http://localhost:8001` instead of `http://localhost:8000`.

To switch back:
```bash
sed -i 's/"8001:8000"/"8000:8000"/' docker-compose.yml
```

### Containers keep restarting

Check the logs:
```bash
docker compose logs mcp_server --tail=50
```

Most common causes:
- `secrets/` directory missing (did not run `generate_secrets.sh`)
- `.env` file missing (did not copy from `.env.example`)
- Alembic migration not run yet (API will 500 until you run it)

### API returns 500 on every request

You have not run the database migration. Run it now:
```bash
docker compose exec mcp_server alembic upgrade head
```

### `generate_secrets.sh` fails or is not found

Make sure you are running the command in **Git Bash**, not in PowerShell or Command Prompt. Git Bash is a separate app installed with Git for Windows - find it in your Start menu.

---

## Stopping and Restarting

```bash
# Stop all services (data is preserved)
docker compose down

# Start again (no rebuild needed)
docker compose up -d

# Stop and delete all data (volumes) - use with care
docker compose down -v
```

---

## Updating TelsonBase

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Run migrations (in case the update added schema changes)
docker compose exec mcp_server alembic upgrade head
```

---

## Development Mode (MailHog)

For local email testing (password reset, user verification), start with the `dev` profile:

```bash
docker compose --profile dev up -d
```

This adds MailHog. Access it at `http://localhost:8025` to view emails sent by the platform. Production deployments omit the `--profile dev` flag and configure real SMTP values in `.env`.

---

## Getting Help

- **Troubleshooting guide:** `docs/Operation Documents/TROUBLESHOOTING.md`
- **GitHub Issues:** https://github.com/QuietFireAI/ClawCoat/issues
- **Email:** support@clawcoat.com

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
