# TelsonBase Troubleshooting Guide

**Version:** 7.3.0CC
**Last Updated:** February 23, 2026
**Architect:** Jeff Phillips — support@telsonbase.com
**AI Model Collaborators:** ChatGPT 3.5/4.0, Gemini 3, Claude Sonnet 4.5, Claude Opus 4.5

---

## Quick Diagnostics

```bash
# Check system health
curl http://localhost:8000/health

# Check all container status
docker-compose ps

# View recent logs
docker-compose logs --tail=50 mcp_server
```

---

## Common Issues

### 1. Docker Daemon Not Starting

**Symptoms:**
- `Cannot connect to the Docker daemon`
- `docker: command not found`

**Solutions:**

**Windows:**
```powershell
# Start Docker Desktop
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Or via services
net start com.docker.service
```

**Linux:**
```bash
sudo systemctl start docker
sudo systemctl enable docker

# Verify
sudo docker run hello-world
```

**macOS:**
```bash
open -a Docker
# Wait for Docker Desktop to fully start (whale icon in menu bar)
```

---

### 2. ValidationError on Startup

**Symptoms:**
```
pydantic_core._pydantic_core.ValidationError: X validation errors for Settings
```

**Common Causes & Fixes:**

**Missing .env file:**
```bash
cp .env.example .env
# Edit .env with your values
```

**ALLOWED_EXTERNAL_DOMAINS format:**
```bash
# WRONG (JSON array)
ALLOWED_EXTERNAL_DOMAINS=["api.anthropic.com","api.perplexity.ai"]

# CORRECT (comma-separated)
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com,api.perplexity.ai,api.venice.ai
```

**CORS_ORIGINS format:**
```bash
# This IS JSON format
CORS_ORIGINS=["https://app.example.com","https://admin.example.com"]

# Or for development (allow all)
CORS_ORIGINS=["*"]
```

**Missing required fields:**
Ensure all these are set in `.env`:
```bash
MCP_API_KEY=your_key_here
JWT_SECRET_KEY=your_secret_here
```

---

### 3. Authentication Failures (401/403)

**Symptoms:**
- `{"detail": "Not authenticated"}`
- `{"detail": "Invalid API key"}`

**Solutions:**

**Check API key is set:**
```bash
# In .env
MCP_API_KEY=your_actual_key

# In request
curl -H "X-API-Key: your_actual_key" http://localhost:8000/v1/system/status
```

**JWT token expired:**
```bash
# Get a new token
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_api_key", "expiration_hours": 24}'
```

**Check JWT_SECRET_KEY warning:**
If you see `WARNING: JWT_SECRET_KEY appears to be insecure`, generate a proper key:
```bash
openssl rand -hex 32
```

---

### 4. Redis Connection Errors

**Symptoms:**
- `ConnectionRefusedError: Connection refused`
- `redis.exceptions.ConnectionError`

**Solutions:**

**Check Redis is running:**
```bash
docker-compose ps redis
# Should show "Up"

# If not running
docker-compose up -d redis
```

**Check Redis connectivity:**
```bash
docker exec -it telsonbase_redis redis-cli ping
# Should return: PONG
```

**Redis data persistence issues:**
```bash
# Check volume exists
docker volume ls | grep redis

# Recreate if corrupted
docker-compose down
docker volume rm telsonbase_redis_data
docker-compose up -d
```

---

### 5. Port Already in Use

**Symptoms:**
- `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solutions:**

**Find what's using the port:**
```bash
# Linux/macOS
lsof -i :8000

# Windows
netstat -ano | findstr :8000
```

**Kill the process or change port:**
```bash
# In docker-compose.yml, change port mapping
ports:
  - "8001:8000"  # Use 8001 instead
```

---

### 6. Tests Failing

**Symptoms:**
- `pytest` returns failures
- Import errors

**Solutions:**

**Install test dependencies:**
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx
```

**Run with verbose output:**
```bash
pytest -v --tb=long tests/
```

**Specific test file:**
```bash
pytest -v tests/test_api.py
```

**Check Python version:**
```bash
python --version
# Requires Python 3.10+
```

---

### 7. Federation Connection Issues

**Symptoms:**
- Trust invitation not processing
- `SSL: CERTIFICATE_VERIFY_FAILED`

**Solutions:**

**Check network connectivity:**
```bash
# From inside container
docker exec -it mcp_server curl -v https://remote-instance.example.com/health
```

**Certificate issues (development):**
For self-signed certs in development, you may need to add the remote instance's CA certificate.

**Firewall rules:**
Ensure ports 80/443 are open between instances.

---

### 8. Anomaly Detection False Positives

**Symptoms:**
- Normal operations triggering anomaly alerts
- Agent getting demoted unexpectedly

**Solutions:**

**Check baseline period:**
New agents need time to establish behavioral baselines. Allow 24-48 hours of normal operation.

**Adjust thresholds:**
```python
# In core/anomaly.py, these can be tuned
RATE_SPIKE_THRESHOLD = 3.0  # Standard deviations
NEW_RESOURCE_SEVERITY = "medium"
```

**Resolve false positives:**
```bash
curl -X POST -H "X-API-Key: $KEY" \
  http://localhost:8000/v1/anomalies/{anomaly_id}/resolve \
  -d '{"resolution_notes": "False positive - batch processing"}'
```

---

### 9. Egress Gateway Blocking Legitimate Requests

**Symptoms:**
- Agent can't reach external API
- `403 Forbidden` from egress gateway

**Solutions:**

**Add domain to whitelist:**
```bash
# In .env
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com,api.perplexity.ai,api.venice.ai,new-api.example.com
```

**Check agent capabilities:**
The agent must also have the capability declared:
```python
CAPABILITIES = [
    "external.read:new-api.example.com",
    "external.write:new-api.example.com",
]
```

---

### 10. Dashboard Not Loading

**Symptoms:**
- Blank page at `/dashboard`
- JavaScript errors in console

**Solutions:**

**Check frontend build:**
```bash
cd frontend
npm install
npm run build
```

**Clear browser cache:**
Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (macOS)

**Check API connectivity:**
Open browser dev tools (F12), check Network tab for failed API calls.

---

## Diagnostic Commands Reference

```bash
# System health
curl http://localhost:8000/health

# Detailed status
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/system/status

# List agents
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/agents/

# Check anomalies
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/anomalies/dashboard/summary

# Verify audit chain
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/audit/chain/verify

# Container logs
docker-compose logs -f mcp_server
docker-compose logs -f redis

# Redis CLI
docker exec -it telsonbase_redis redis-cli

# Enter container shell
docker exec -it mcp_server /bin/bash
```

---

## Python/Pip Dependency Issues

### 11. Module Import Errors

**Symptoms:**
- `ModuleNotFoundError: No module named 'xyz'`
- `ImportError: cannot import name 'ABC' from 'xyz'`

**Solutions:**

**Install missing dependencies:**
```bash
pip install -r requirements.txt

# If using virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**Version conflicts:**
```bash
# Check for conflicts
pip check

# Reinstall with fresh environment
pip install --force-reinstall -r requirements.txt
```

**Pydantic v1 vs v2 issues:**
```bash
# TelsonBase uses Pydantic v2 with pydantic-settings
pip install pydantic>=2.0.0 pydantic-settings>=2.0.0
```

---

### 12. Virtual Environment Issues

**Symptoms:**
- Wrong Python version being used
- Packages installed globally instead of in venv
- `pip` not found after activation

**Solutions:**

**Create fresh virtual environment:**
```bash
# Remove old venv
rm -rf venv  # Linux/macOS
rmdir /s /q venv  # Windows

# Create new with correct Python
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Verify correct Python:**
```bash
which python  # Should show venv path
python --version  # Should be 3.10+
```

---

### 13. Network/Firewall Issues

**Symptoms:**
- `ConnectionError: Cannot connect to host`
- `TimeoutError: Connection timed out`
- Federation trust establishment failing

**Solutions:**

**Check basic connectivity:**
```bash
# Test from host
curl -v http://localhost:8000/health

# Test from inside container
docker exec -it mcp_server curl -v http://localhost:8000/health
```

**Firewall rules (Linux):**
```bash
# Check if ports are blocked
sudo iptables -L -n | grep 8000

# Allow port (if needed)
sudo ufw allow 8000/tcp
```

**Windows Firewall:**
```powershell
# Check if port is allowed
Get-NetFirewallRule | Where-Object { $_.LocalPort -eq 8000 }

# Add rule if needed
New-NetFirewallRule -DisplayName "TelsonBase API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Docker network issues:**
```bash
# Inspect network
docker network ls
docker network inspect telsonbase_backend

# Recreate networks
docker-compose down
docker network prune
docker-compose up -d
```

**Proxy/Corporate firewall:**
```bash
# Check if proxy is blocking
curl -v --proxy "" http://localhost:8000/health

# Configure Docker to use proxy
# Edit ~/.docker/config.json or Docker Desktop settings
```

---

### 14. SSL/TLS Certificate Issues

**Symptoms:**
- `SSL: CERTIFICATE_VERIFY_FAILED`
- `SSLError: certificate verify failed`

**Solutions:**

**Development (self-signed certs):**
```bash
# Disable SSL verification (DEVELOPMENT ONLY)
export CURL_CA_BUNDLE=""
curl -k https://localhost:8443/health
```

**Production certificates:**
```bash
# Verify certificate chain
openssl s_client -connect your-domain.com:443 -showcerts

# Check certificate expiry
openssl x509 -in cert.pem -noout -enddate
```

**Let's Encrypt with Traefik:**
Ensure `TRAEFIK_ACME_EMAIL` is set in `.env` for automatic certificate provisioning.

---

## Getting Help

1. **Check existing issues:** [GitHub Issues](https://github.com/quietfire/telsonbase/issues)
2. **Search documentation:** Check `docs/` folder
3. **Open new issue:** Use bug report template
4. **Email:** support@telsonbase.com

When reporting issues, include:
- TelsonBase version (`curl http://localhost:8000/health`)
- Docker version (`docker --version`)
- Python version (`python --version`)
- Relevant logs (`docker-compose logs --tail=100 mcp_server`)
- Steps to reproduce

---

*"When in doubt, check the logs."* — Quietfire AI
