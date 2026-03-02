# TelsonBase Installation Guide for Windows

**Version:** 7.4.0CC
**Target Audience:** Windows users, including those new to Docker

---

## Prerequisites

### 1. Install Docker Desktop for Windows

Docker Desktop is required to run TelsonBase.

**Download:** https://www.docker.com/products/docker-desktop/

**System Requirements:**
- Windows 10 64-bit: Pro, Enterprise, or Education (Build 19041+)
- Windows 11 64-bit: Home, Pro, Enterprise, or Education
- WSL 2 backend (recommended)
- 4GB RAM minimum (8GB+ recommended for Ollama/LLM)

**Installation Steps:**
1. Download Docker Desktop installer
2. Run the installer (may require admin privileges)
3. Follow the installation wizard
4. Restart your computer when prompted
5. Launch Docker Desktop from Start menu
6. Wait for Docker to fully start (whale icon in system tray)

**Verify Installation:**
```powershell
docker --version
docker compose version
```

> **Note:** TelsonBase uses the modern `docker compose` (V2 plugin, no hyphen). The legacy `docker-compose` command is not required.

### 2. Install Git (Optional but Recommended)

**Download:** https://git-scm.com/download/win

Or use winget:
```powershell
winget install Git.Git
```

---

## Installation

### Option A: Clone from GitHub (Recommended)

```powershell
# Open PowerShell or Command Prompt
git clone https://github.com/quietfire/telsonbase.git
cd telsonbase
```

### Option B: Download ZIP

1. Go to https://github.com/quietfire/telsonbase
2. Click "Code" → "Download ZIP"
3. Extract to a folder (e.g., `C:\telsonbase`)
4. Open PowerShell/Command Prompt in that folder

---

## Configuration

### 1. Create Environment File

```powershell
# Copy the example environment file
copy .env.example .env
```

### 2. Generate Secure Keys

Open PowerShell and generate random keys:

```powershell
# Generate API key (copy output to .env)
-join ((1..64) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })

# Or use OpenSSL if installed
openssl rand -hex 32
```

### 3. Edit .env File

Open `.env` in Notepad or your preferred editor:

```powershell
notepad .env
```

**Required Changes:**
```env
# Replace these with your generated keys
MCP_API_KEY=paste_your_generated_key_here
JWT_SECRET_KEY=paste_another_generated_key_here

# For local development
TRAEFIK_DOMAIN=localhost
```

**Save the file.**

---

## Starting TelsonBase

### 1. Ensure Docker Desktop is Running

Look for the Docker whale icon in your system tray. It should show "Docker Desktop is running."

### 2. Start the Services

```powershell
# From the telsonbase directory
docker compose up -d --build
```

**First run will take several minutes** as Docker downloads and builds images.

### 3. Verify Startup

```powershell
# Check all containers are running
docker compose ps

# Test the health endpoint
curl http://localhost:8000/health
```

If `curl` isn't available:
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health
```

Or open a browser to: http://localhost:8000/health

Expected response:
```json
{"status": "healthy", "version": "7.4.0CC", ...}
```

### 4. Pull the AI Model (Required for LLM Features)

TelsonBase uses Ollama for local AI inference. After startup, pull the default model:

```powershell
# Pull gemma2:9b (default model — ~5.4 GB download)
docker exec telsonbase-ollama-1 ollama pull gemma2:9b
```

This is a one-time step. The model persists in the `ollama_data` volume across restarts.

**Verify the model is available:**
```powershell
curl http://localhost:11434/api/tags
```

---

## Accessing TelsonBase

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | http://localhost:8000/dashboard | Security management UI |
| **User Console** | http://localhost:8000/console | Operator-focused UI |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **Health Check** | http://localhost:8000/health | System status |
| **MCP Gateway** | http://localhost:8000/mcp | Goose / Claude Desktop connection point (operator tool) |

### First Login to Dashboard

1. Open http://localhost:8000/dashboard
2. Enter your API key (from `.env` file, `MCP_API_KEY` value)
3. You'll see the security dashboard

---

## Running the Test Suites

TelsonBase includes two test runners. Both require the `MCP_API_KEY` environment variable to be set in your session.

### Set API Key in Session

```powershell
# In PowerShell (use your actual key from .env)
$env:MCP_API_KEY = "your-api-key-here"

# In Command Prompt
set MCP_API_KEY=your-api-key-here
```

### Basic Validation Suite

Runs 21 core tests — authentication, API health, audit chain, agents, compliance.

```powershell
./run_tests.bat
```

All 21 tests should PASS before proceeding to advanced testing.

### Advanced Test Suite

Runs 20 test groups across 5 levels: security, chaos/resilience, schema validation, performance, and static analysis. Takes 60–90 minutes (includes LLM inference tests).

```powershell
./run_advanced_tests.bat
```

> **Note:** The advanced suite includes LLM inference tests (S2) that run on CPU and may take several minutes per call. This is normal.

---

## Common Windows Issues

### "Docker daemon is not running"

**Solution:**
1. Open Docker Desktop from Start menu
2. Wait for it to fully start (may take 1-2 minutes)
3. Try the command again

### "Port already in use"

**Solution:**
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with the number from above)
taskkill /PID <PID> /F
```

Or change the port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead
```

### "WSL 2 installation is incomplete"

**Solution:**
1. Open PowerShell as Administrator
2. Run: `wsl --install`
3. Restart your computer
4. Reopen Docker Desktop

### "Hyper-V is not enabled"

**Solution:**
1. Open "Turn Windows features on or off"
2. Enable "Hyper-V" and "Windows Hypervisor Platform"
3. Restart your computer

### Containers keep restarting

**Check logs:**
```powershell
docker compose logs mcp_server
```

**Common causes:**
- Missing `.env` file (copy from `.env.example`)
- Invalid `.env` values (check format)
- Port conflicts

### run_tests.bat shows "MCP_API_KEY not set"

You must set the API key in your shell before running the bat file:
```powershell
$env:MCP_API_KEY = "your-api-key-here"
./run_tests.bat
```

---

## Stopping TelsonBase

```powershell
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v
```

---

## Updating TelsonBase

```powershell
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build
```

---

## Getting Help

1. **Documentation:** See `docs/` folder
2. **Troubleshooting:** See `docs/Operation Documents/TROUBLESHOOTING.md`
3. **Issues:** https://github.com/quietfire/telsonbase/issues
4. **Email:** support@telsonbase.com

---

*TelsonBase v7.4.0CC — Protecting the telson through human-AI collaboration.*
