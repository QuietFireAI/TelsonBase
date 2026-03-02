# TelsonBase Testing Guide

Everything you need to verify the system works.

## Quick Start

```bash
# 1. Start the stack
docker compose up -d --build

# 2. Wait for services to be healthy (about 30 seconds)
docker compose ps

# 3. Seed demo data (populates dashboard with sample data)
docker compose exec mcp_server python scripts/seed_demo_data.py

# 4. Open dashboard
# http://localhost:8000/dashboard
# API Key: (from your .env file, default: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D)
```

---

## Test 1: API Integration Test

Verifies all API endpoints work correctly.

```bash
# Run from host (requires Python 3.8+ with requests installed)
pip install requests
python scripts/test_security_flow.py

# Or run inside the container
docker compose exec mcp_server python scripts/test_security_flow.py
```

**Expected output:**
```
[PASS] API responds to /health
[PASS] Protected endpoint rejects no auth
[PASS] Protected endpoint accepts valid auth
[PASS] Agent list endpoint works
... (all tests should pass)
```

---

## Test 2: Unit Tests (pytest)

Runs the test suite for signing, capabilities, and API.

```bash
# Run inside container
docker compose exec mcp_server pytest -v

# With coverage
docker compose exec mcp_server pytest --cov=. --cov-report=term-missing

# Specific test file
docker compose exec mcp_server pytest tests/test_signing.py -v
```

**Note:** Unit tests require Redis. The test suite uses Redis DB 15 to avoid conflicts.

---

## Test 3: Dashboard Verification

Manual verification that the UI works.

1. Open http://localhost:8000/dashboard
2. Enter API key
3. Verify you see:
   - Overview with status cards
   - Pending approvals (if data seeded)
   - Anomalies list
   - Registered agents
   - Federation relationships

---

## Test 4: Agent Security Flow

Demonstrates the complete security flow with a working agent.

```bash
# 1. Make sure stack is running
docker compose up -d

# 2. Dispatch a task to the demo agent
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "demo_agent.list_files",
    "args": ["/app/demo/input"],
    "kwargs": {}
  }'

# 3. Check task status (replace TASK_ID with returned ID)
curl -X GET "http://localhost:8000/v1/tasks/TASK_ID" \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D"

# 4. Test capability denial (this should FAIL - blocked by security)
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "demo_agent.attempt_unauthorized",
    "args": ["/etc/passwd"],
    "kwargs": {}
  }'

# Expected: Task runs but returns "Permission denied" - capability system working
```

---

## Test 5: Approval Flow

Tests human-in-the-loop approval gates.

```bash
# 1. Request a delete operation (requires approval)
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "demo_agent.delete_file",
    "args": ["/app/demo/output/test.txt"],
    "kwargs": {}
  }'

# 2. Check approvals in dashboard
# http://localhost:8000/dashboard -> Approvals tab

# 3. Or via API
curl -X GET http://localhost:8000/v1/approvals/ \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D"

# 4. Approve the request (replace REQUEST_ID)
curl -X POST http://localhost:8000/v1/approvals/REQUEST_ID/approve \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{"decided_by": "admin", "notes": "Approved for testing"}'
```

---

## Test 6: Federation (Two Instances)

Tests cross-instance trust establishment.

```bash
# 1. Start federation test environment (two independent instances)
docker compose -f docker compose.federation-test.yml up -d --build

# 2. Wait for both instances to be healthy
docker compose -f docker compose.federation-test.yml ps

# 3. Run federation test script
python scripts/test_federation.py

# 4. Access both dashboards:
#    Instance A: http://localhost:8001/dashboard (key: alpha_secret_key_12345)
#    Instance B: http://localhost:8002/dashboard (key: beta_secret_key_67890)

# 5. Clean up
docker compose -f docker compose.federation-test.yml down -v
```

---

## Test 7: Backup Agent

Tests the working backup agent.

```bash
# 1. Create some test data
docker compose exec mcp_server mkdir -p /data/test_volume
docker compose exec mcp_server sh -c 'echo "Test data" > /data/test_volume/file.txt'

# 2. List available volumes
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{"task_name": "backup_agent.list_volumes", "args": [], "kwargs": {}}'

# 3. Create a backup
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{"task_name": "backup_agent.create_backup", "args": ["test_volume"], "kwargs": {}}'

# 4. List backups
curl -X POST http://localhost:8000/v1/tasks/dispatch \
  -H "X-API-Key: My_Api_Key_8C7F447616D37CC656BFF2A2AC21D" \
  -H "Content-Type: application/json" \
  -d '{"task_name": "backup_agent.list_backups", "args": [], "kwargs": {}}'
```

---

## Troubleshooting

### Container won't start
```bash
docker compose logs mcp_server
docker compose logs worker
```

### Redis connection errors
```bash
docker compose ps redis
docker compose logs redis
```

### Tests fail with import errors
```bash
# Rebuild the container
docker compose down
docker compose up -d --build
```

### Dashboard shows empty data
```bash
# Seed demo data
docker compose exec mcp_server python scripts/seed_demo_data.py
```

---

## What Each Test Verifies

| Test | Verifies |
|------|----------|
| API Integration | All endpoints work, auth blocks unauthorized |
| Unit Tests | Signing, capabilities, API logic |
| Dashboard | UI renders, connects to API |
| Agent Security | Capabilities block unauthorized access |
| Approval Flow | Human-in-the-loop gates work |
| Federation | Cross-instance trust establishment |
| Backup Agent | Working agent demonstrates full flow |

---

## Clean Slate Reset

If you need to start completely fresh:

```bash
docker compose down -v
docker system prune -f
docker compose up -d --build
```
