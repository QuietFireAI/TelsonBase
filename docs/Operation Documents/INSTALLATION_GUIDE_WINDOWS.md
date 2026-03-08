# TelsonBase - Installation Guide for Windows

**Version:** v11.0.1 · **Maintainer:** Quietfire AI
**Target Audience:** Windows users, including those new to Docker

---

## Before You Start

TelsonBase runs entirely in Docker. You do not install Python, Redis, or any other dependency directly on Windows — Docker handles all of that. What you need on your machine:

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
- 8 GB RAM minimum — Ollama (local LLM) needs headroom
- WSL 2 backend (recommended — Docker will prompt you to enable it)

**Steps:**
1. Run the installer — it may ask for administrator privileges
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
git clone https://github.com/QuietFireAI/TelsonBase.git
cd TelsonBase
```

> Note the capital T — the directory is `TelsonBase`, not `telsonbase`.

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

Open **Git Bash** (from the Start menu — not PowerShell) and run:

```bash
bash scripts/generate_secrets.sh
```

This script does three things:
- Generates cryptographically random keys for the API, JWT, encryption, and all service passwords
- Writes them into the `secrets/` directory as Docker secret files
- Updates your `.env` file with the matching values

**Do not skip this step and do not generate keys manually.** TelsonBase uses Docker Secrets — keys must be in `secrets/` as files, not just in `.env`. The script handles both.

After the script completes, verify the secrets directory was created:

```bash
ls secrets/
```

You should see files including `telsonbase_mcp_api_key`. That file's contents are your API key — keep it.

```bash
cat secrets/telsonbase_mcp_api_key
```

### Step 3 - Review .env (optional but recommended)

Open `.env` in any editor and review the values. The defaults work for local development. The one setting you may want to change:

```env
# Enable the full 8-step governance pipeline
# Set to true to use OpenClaw agent governance features
OPENCLAW_ENABLED=true
```

Set `OPENCLAW_ENABLED=true` if you want the full governance pipeline active (trust levels, kill switch, Manners compliance). Leave it `false` if you are exploring the platform for the first time — the platform runs fine without it, but agent governance features will not fire.

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

All 12 services should show **Up** or **healthy**:

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
3. Enter your API key — find it with:
   ```bash
   cat secrets/telsonbase_mcp_api_key
   ```
4. Click **Connect** — the header will switch to **Live** and show the system health dot

---

## Running the Test Suite

TelsonBase ships with 720 tests. Run them from inside the Docker container:

```bash
docker compose exec mcp_server python -m pytest tests/ -v
```

Expected result: **720 passed, 1 skipped, 0 failed**

The 1 skip is expected — it is an Alembic idempotency test that requires a live database in a specific state. Everything else should be green.

Run only the security battery (96 tests):
```bash
docker compose exec mcp_server python -m pytest tests/security/ -v
```

Run a specific test file:
```bash
docker compose exec mcp_server python -m pytest tests/test_auth.py -v
```

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

Alternatively, edit `docker-compose.yml` to use a different host port:
```yaml
ports:
  - "8001:8000"  # access via localhost:8001 instead
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

Make sure you are running the command in **Git Bash**, not in PowerShell or Command Prompt. Git Bash is a separate app installed with Git for Windows — find it in your Start menu.

---

## Stopping and Restarting

```bash
# Stop all services (data is preserved)
docker compose down

# Start again (no rebuild needed)
docker compose up -d

# Stop and delete all data (volumes) — use with care
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
- **GitHub Issues:** https://github.com/QuietFireAI/TelsonBase/issues
- **Email:** support@telsonbase.com

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
