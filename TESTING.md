# TelsonBase Testing Guide

**Version:** v11.0.1 | **Tests Passing:** 720 (1 skipped) | **Updated:** March 8, 2026

---

## The Short Version

```bash
# Run the full test suite
docker compose exec mcp_server python -m pytest tests/ -v --tb=short \
  --ignore=tests/test_mqtt_stress.py

# Run the governance smoke test (11 live checks against the running stack)
./scripts/governance_smoke_test.sh
```

Both complete clean on a healthy deployment. If either fails, the output tells you exactly what and where.

---

## Prerequisites

Before running any tests:

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env — at minimum, replace CHANGE_ME values

# 2. Generate secrets
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh

# 3. Start the stack (dev includes MailHog)
docker compose --profile dev up -d --build

# 4. Run database migrations (required on first start — API returns 500 without this)
docker compose exec mcp_server alembic upgrade head

# 5. Enable governance pipeline (required for OpenClaw tests)
# Set OPENCLAW_ENABLED=true in .env, then restart
docker compose restart mcp_server
```

**API key location:**
```bash
cat secrets/telsonbase_mcp_api_key
```

Use this key as `X-API-Key` in all curl examples below.

---

## 1. Full Test Suite — 720 Tests

The complete automated test suite covering all platform layers.

```bash
# Full run (excludes MQTT stress tests — run separately if needed)
docker compose exec mcp_server python -m pytest tests/ -v --tb=short \
  --ignore=tests/test_mqtt_stress.py

# With coverage report
docker compose exec mcp_server python -m pytest tests/ --cov=. \
  --cov-report=term-missing --ignore=tests/test_mqtt_stress.py
```

**Expected result:** `720 passed, 1 skipped`

**The 1 skipped:** `test_contracts.py::TestOperationalContracts::test_alembic_upgrade_head_is_idempotent` — skips when `DATABASE_URL` is not set in the test environment. This test verifies that running `alembic upgrade head` twice on an already-migrated database is a no-op. It requires a live database connection to run and skips gracefully without one. Not a failure — by design.

To run it explicitly with a live DB:
```bash
DATABASE_URL=postgresql://user:pass@localhost/telsonbase \
  docker compose exec mcp_server python -m pytest \
  tests/test_contracts.py::TestOperationalContracts::test_alembic_upgrade_head_is_idempotent -v
```

### Suite Breakdown

| File | Tests | What It Covers |
|---|---|---|
| `test_security_battery.py` | 96 | Authentication, encryption, access control, audit trail, network security, data protection, compliance, cryptography, runtime boundaries |
| `test_qms.py` | 115 | QMS™ protocol — block detection, chain build/parse, halt chains, validation, security flagging, spec examples |
| `test_toolroom.py` | 129 | Toolroom and Foreman — checkout lifecycle, HITL approval, manifests, function tools, trust-gated execution |
| `test_openclaw.py` | 55 | OpenClaw governance — registration, evaluate_action pipeline, trust promotion/demotion, kill switch, Manners scoring |
| `test_identiclaw.py` | 50 | IdentiClaw identity — DID parsing, Ed25519 verification, verifiable credentials, auth flow |
| `test_ollama.py` | 49 | Ollama LLM — service init, health, model listing, text generation, chat completion |
| `test_secrets.py` | 48 | Secrets management — SecretValue masking, SecretsProvider resolution, production startup guard |
| `test_observability.py` | 40 | Prometheus metrics, MQTT bus, agent message events, monitoring config |
| `test_behavioral.py` | 30 | GIVEN/WHEN/THEN behavioral tests — model fallback, QMS™ protocol discipline, security boundaries, trust progression |
| `test_e2e_integration.py` | 29 | End-to-end — full user lifecycle, tenant isolation, audit chain integrity, error sanitization |
| `test_integration.py` | 26 | Cross-system — federation handshake, egress blocking, approval workflow, anomaly detection |
| `test_api.py` | 19 | REST API surface — public endpoints, auth requirements, QMS™ conventions |
| `test_capabilities.py` | 15 | Capability enforcement — Capability, CapabilitySet, CapabilityEnforcer |
| `test_signing.py` | 13 | Message signing — SignedAgentMessage, AgentKeyRegistry, MessageSigner, tamper detection |
| `test_contracts.py` | 7 | Enum contract tripwires — TenantType (7 types), AgentTrustLevel (5 tiers), version format |
| `test_mqtt_stress.py` | 26 | MQTT stress (excluded from standard run — run separately, requires broker load) |

### Run a Single Suite

```bash
docker compose exec mcp_server python -m pytest tests/test_openclaw.py -v --tb=short
```

### Run a Single Test Class

```bash
docker compose exec mcp_server python -m pytest tests/test_openclaw.py::TestGovernancePipeline -v --tb=short
```

### Run a Single Test Function

```bash
docker compose exec mcp_server python -m pytest tests/test_openclaw.py::TestKillSwitch::test_suspend_and_reinstate -v --tb=short
```

---

## 2. Security Battery — 96 Tests

The dedicated security test suite. Run in isolation to verify the security posture.

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py -v --tb=short
```

**Expected result:** `96 passed`

### Security Battery by Category

```bash
# Authentication — 19 tests (SHA-256 key hashing, JWT, MFA, sessions)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestAuthSecurity -v

# Encryption — 11 tests (AES-256-GCM, PBKDF2, HMAC correctness)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestEncryptionIntegrity -v

# Access Control — 13 tests (RBAC enforcement, custom grants/denials)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestAccessControl -v

# Audit Trail — 11 tests (SHA-256 chain, tamper detection, UTC timestamps)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestAuditTrailIntegrity -v

# Network — 9 tests (CORS, Redis auth, production mode, MQTT)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestNetworkSecurity -v

# Data Protection — 11 tests (PHI de-identification, 18 safe harbor identifiers)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestDataProtection -v

# Compliance — 11 tests (HITRUST, BAA lifecycle, breach notification)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestComplianceInfrastructure -v

# Cryptography — 8 tests (algorithm verification, key sizes, RFC 6238 TOTP)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestCryptographicStandards -v

# Runtime Boundaries — 3 tests (rate limiter, CAPTCHA expiry, email token expiry)
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestRuntimeBoundaries -v
```

---

## 3. Governance Smoke Test — 11 Live Checks

The most important post-deploy verification. Exercises the live governance pipeline end-to-end with a real agent.

**Requires:** `OPENCLAW_ENABLED=true` in `.env` and a running stack.

```bash
# Local (reads API key from secrets/ automatically)
./scripts/governance_smoke_test.sh

# Remote server
API_KEY=your_key API_BASE=http://your-server:8000 ./scripts/governance_smoke_test.sh

# Inside the container
docker compose exec mcp_server bash /app/scripts/governance_smoke_test.sh
```

**What it verifies:**

| Step | Check |
|---|---|
| 1 | API liveness + Redis health |
| 2 | New agent starts at QUARANTINE |
| 3 | QUARANTINE: internal read BLOCKED |
| 4 | QUARANTINE: external write BLOCKED |
| 5 | Human promotion: QUARANTINE → PROBATION |
| 6 | PROBATION: internal read ALLOWED (autonomous) |
| 7 | PROBATION: external write GATED (HITL required) |
| 8 | Kill switch: agent suspended |
| 9 | Suspended agent: all actions BLOCKED |
| 10 | Reinstatement restores governance |
| 11 | Audit chain accessible, SHA-256 hash chain intact |

**Expected result:** `11/11 passed`

---

## 4. OpenClaw Governance — Manual Verification

Step-by-step curl verification of the trust tier system.

```bash
API_KEY=$(cat secrets/telsonbase_mcp_api_key)
BASE=http://localhost:8000
```

### Register an Agent

```bash
curl -s -X POST $BASE/v1/openclaw/register \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-agent", "api_key": "test-key-abc123"}'
```

**Expected:** `trust_level: "quarantine"` — every new agent starts here, no exceptions.

Save the `instance_id` from the response as `$ID` for subsequent calls.

### Evaluate an Action (QUARANTINE — should block)

```bash
curl -s -X POST $BASE/v1/openclaw/$ID/action \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/data/test.txt"}}'
```

**Expected:** `"allowed": false` — QUARANTINE blocks everything.

### Promote to PROBATION

```bash
curl -s -X POST $BASE/v1/openclaw/$ID/promote \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"new_level": "probation", "reason": "Manual test promotion"}'
```

### Evaluate External Action (PROBATION — should gate)

```bash
curl -s -X POST $BASE/v1/openclaw/$ID/action \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "http_post", "tool_args": {"url": "https://api.example.com", "body": "data"}}'
```

**Expected:** `"allowed": false, "approval_required": true` — PROBATION gates external calls to HITL.

### Kill Switch

```bash
# Suspend
curl -s -X POST $BASE/v1/openclaw/$ID/suspend \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing kill switch"}'

# Verify hard block — any action attempt should return allowed: false
curl -s -X POST $BASE/v1/openclaw/$ID/action \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/data/test.txt"}}'

# Reinstate
curl -s -X POST $BASE/v1/openclaw/$ID/reinstate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test complete"}'
```

### Trust Report

```bash
curl -s $BASE/v1/openclaw/$ID/trust-report \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

Returns: trust tier, Manners compliance score, capability matrix, action counts, suspension status.

### Full Trust Tier Ladder

```bash
# Promote through all 5 tiers (each requires human approval in production)
# QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT
for level in probation resident citizen agent; do
  curl -s -X POST $BASE/v1/openclaw/$ID/promote \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"new_level\": \"$level\", \"reason\": \"Ladder test\"}"
  echo "Promoted to $level"
done
```

---

## 5. Audit Chain Verification

```bash
API_KEY=$(cat secrets/telsonbase_mcp_api_key)
BASE=http://localhost:8000

# Chain status
curl -s $BASE/v1/audit/chain/status -H "X-API-Key: $API_KEY" | python3 -m json.tool

# Verify last 50 entries (checks SHA-256 hash linkage)
curl -s "$BASE/v1/audit/chain/verify?entries=50" -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

**Expected:** `chain_breaks: []` — zero breaks means the hash chain is intact and no entries have been tampered with or deleted.

---

## 6. MCP Gateway — 13 Tools

Verify the MCP server is live and all 13 tools are registered.

```bash
curl -s http://localhost:8000/mcp \
  -H "X-API-Key: $(cat secrets/telsonbase_mcp_api_key)"
```

Expected: JSON list of 13 tools including `openclaw_register`, `openclaw_evaluate_action`, `openclaw_promote`, `openclaw_suspend`, `openclaw_reinstate`, `audit_chain_verify`, and others.

**Goose integration test:**
```bash
# From goose.yaml — point your MCP client at:
# http://localhost:8000/mcp
# with X-API-Key header set to your API key
goose session --profile telsonbase
```

---

## 7. Proof Sheet Spot Check

787 proof documents exist. Spot-check any claim against live code by running its verification command.

**Verify a specific claim:**
```bash
# Pick any proof sheet — read the Verification Command section and run it
# Example: verify the kill switch claim
docker compose exec mcp_server python -m pytest \
  tests/test_openclaw.py::TestKillSwitch -v --tb=short

# Example: verify a single individual test sheet
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py::TestAuthSecurity::test_api_key_hash_uses_sha256 \
  -v --tb=short
```

**Spot-check a random individual sheet:**
```bash
# Pick a random sheet from any subdirectory
ls proof_sheets/individual/sec/ | shuf | head -1
# Read the sheet, run its verification command
```

**Full manifest:** See `proof_sheets/TB-PROOF-052_full_test_manifest.md` for every file, class, and function name.

---

## 8. QMS™ Protocol Verification

Verify QMS™ chain construction and parsing is working correctly.

```bash
# Run the full QMS test suite
docker compose exec mcp_server python -m pytest tests/test_qms.py -v --tb=short

# Run the spec examples specifically (canonical ping, halt, failure, clarification)
docker compose exec mcp_server python -m pytest tests/test_qms.py::TestSpecExamples -v --tb=short

# Verify security flagging — non-QMS messages detected
docker compose exec mcp_server python -m pytest tests/test_qms.py::TestSecurityFlagging -v --tb=short
```

**Expected:** `115 passed`

---

## 9. Dashboard Verification

Manual UI check after stack is running.

1. Open `http://localhost:8000/dashboard`
2. Enter API key from `secrets/telsonbase_mcp_api_key`
3. Verify:
   - Overview cards show agent count, pending approvals, anomaly count
   - Agents tab shows registered agents with trust tier pills
   - Audit Chain tab shows entries with chain ID (copyable), verify button functional
   - Approvals tab shows pending requests (if any)
   - Anomalies tab shows detected events
4. Register an agent via API, confirm it appears in the dashboard at QUARANTINE
5. Promote the agent, confirm tier pill updates

**Chain ID copy:** Click the copy icon next to a chain ID — full SHA-256 hash should reach clipboard. Verify button runs the hash check inline.

---

## 10. MQTT Stress Tests

Excluded from the standard run — requires sustained broker load.

```bash
# Run separately when broker capacity testing is needed
docker compose exec mcp_server python -m pytest tests/test_mqtt_stress.py -v --tb=short
```

26 tests. Not part of the 720 count.

---

## 11. Federation — Two Instances

Tests cross-instance trust establishment.

```bash
# Start two-instance federation environment
docker compose -f docker-compose.federation-test.yml up -d --build

# Verify both instances healthy
docker compose -f docker-compose.federation-test.yml ps

# Run federation test
python scripts/test_federation.py

# Dashboards
#   Instance A: http://localhost:8001/dashboard
#   Instance B: http://localhost:8002/dashboard

# Clean up
docker compose -f docker-compose.federation-test.yml down -v
```

---

## 12. Troubleshooting

### API returns 500 on first start
```bash
# Migrations not applied — run:
docker compose exec mcp_server alembic upgrade head
```

### Governance pipeline not enforcing (all actions allowed)
```bash
# OPENCLAW_ENABLED must be true
grep OPENCLAW_ENABLED .env
# If false:
sed -i 's/OPENCLAW_ENABLED=false/OPENCLAW_ENABLED=true/' .env
docker compose restart mcp_server
sleep 4
./scripts/governance_smoke_test.sh
```

### Tests fail: Redis connection errors
```bash
docker compose ps redis
docker compose logs redis
# Redis must be healthy before running tests
```

### Tests fail: import errors
```bash
# Rebuild the container — dependency may have changed
docker compose down
docker compose up -d --build
docker compose exec mcp_server alembic upgrade head
```

### Container name not found
```bash
# Correct container name:
docker compose exec mcp_server ...
# Not: docker exec mcp_server ...
```

### Smoke test: OpenClaw steps skip
```bash
# OpenClaw is disabled — enable it:
sed -i 's/OPENCLAW_ENABLED=false/OPENCLAW_ENABLED=true/' .env
docker compose restart mcp_server && sleep 4
./scripts/governance_smoke_test.sh
```

### Dashboard shows empty data
```bash
# Seed demo data
docker compose exec mcp_server python scripts/seed_demo_data.py
```

### MailHog not available
```bash
# MailHog requires --profile dev
docker compose --profile dev up -d
# Without --profile dev, production SMTP vars in .env are used instead
```

---

## 13. Clean Slate Reset

```bash
docker compose down -v
docker system prune -f
docker compose --profile dev up -d --build
docker compose exec mcp_server alembic upgrade head
```

---

## What Each Test Layer Covers

| Layer | Command | Verifies |
|---|---|---|
| Full suite | `pytest tests/ --ignore=test_mqtt_stress.py` | All 720 tests — every platform layer |
| Security battery | `pytest tests/test_security_battery.py` | 96 dedicated security checks |
| Governance smoke | `./scripts/governance_smoke_test.sh` | Live trust tier pipeline end-to-end |
| Audit chain | `GET /v1/audit/chain/verify` | SHA-256 hash linkage intact |
| MCP gateway | `GET /mcp` | 13 tools registered and live |
| QMS™ suite | `pytest tests/test_qms.py` | Protocol grammar, security flagging, spec examples |
| Proof spot check | Individual pytest command from any sheet | Specific claim verified against live code |

---

*TelsonBase v11.0.1 — Quietfire AI — March 8, 2026*
