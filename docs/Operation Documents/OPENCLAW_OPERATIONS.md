# OpenClaw Operations Guide

## TelsonBase v7.4.0CC — "Control Your Claw"

**Architecture:** TelsonBase acts as a governed MCP proxy. OpenClaw is never modified — TelsonBase wraps it. Every action the claw wants to take is evaluated through an 8-step governance pipeline before execution.

---

## Quick Start

### 1. Enable the Integration

In `.env`, flip the master switch:

```
OPENCLAW_ENABLED=true
```

Rebuild and restart the API server:

```powershell
docker compose build mcp_server && docker compose up -d mcp_server worker beat
```

Verify in logs:

```powershell
docker compose logs mcp_server | grep -i openclaw
# Should see: "REM: OpenClaw governance engine initialized"
```

Verify via API:

```powershell
curl -H "X-API-Key: $env:MCP_API_KEY" http://localhost:8000/v1/openclaw/list
# Should return: {"instances": [], "count": 0, ...}
# (NOT a 404 — 404 means OPENCLAW_ENABLED is still false)
```

---

## The Trust Level Model — The Secret Sauce

Every claw starts at QUARANTINE. Trust is earned, not given. There are no shortcuts — promotion moves one level at a time.

| Level | Who it's for | Autonomous actions | Gated actions |
|---|---|---|---|
| **QUARANTINE** | New claws, untrusted | None — everything requires approval | All actions |
| **PROBATION** | Claws building a record | Internal read-only tools | All external calls |
| **RESIDENT** | Established claws | Most internal operations | High-risk / destructive |
| **CITIZEN** | Fully trusted claws | Almost everything | Anomaly-flagged only |
| **AGENT** | Apex tier — fully verified autonomous designation | Full autonomy, 300 actions/min | None |

Promotion path: `QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT` (one step at a time)
Demotion: can go to any lower level instantly (no step limit)

---

## Register a Claw

Register a new OpenClaw instance. It starts at QUARANTINE automatically.

```powershell
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"name": "my-claw-instance", "api_key": "claw-secret-key-here", "allowed_tools": [], "blocked_tools": []}' `
  http://localhost:8000/v1/openclaw/register
```

**Response:**
```json
{
  "instance_id": "claw_abc123def456",
  "name": "my-claw-instance",
  "trust_level": "quarantine",
  "manners_score": 1.0,
  "action_count": 0,
  "suspended": false,
  "qms_status": "Thank_You"
}
```

Save the `instance_id` — you'll use it for all subsequent operations.

---

## Submit an Action for Governance Evaluation

This is the core operation. When an OpenClaw instance wants to do something, it submits the action to TelsonBase, which runs it through the 8-step pipeline and returns a decision.

```powershell
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"tool_name": "read_file", "tool_args": {"path": "/docs/report.txt"}}' `
  http://localhost:8000/v1/openclaw/claw_abc123def456/action
```

**Response — Allowed:**
```json
{
  "allowed": true,
  "reason": "Action permitted at RESIDENT trust level",
  "action_category": "read",
  "trust_level_at_decision": "resident",
  "approval_required": false,
  "manners_score_at_decision": 0.92,
  "anomaly_flagged": false,
  "qms_status": "Thank_You"
}
```

**Response — Gated (approval required):**
```json
{
  "allowed": false,
  "reason": "External action requires approval at PROBATION trust level",
  "action_category": "external",
  "trust_level_at_decision": "probation",
  "approval_required": true,
  "approval_id": "appr_xyz789",
  "manners_score_at_decision": 0.88,
  "anomaly_flagged": false,
  "qms_status": "Excuse_Me"
}
```

**Response — Blocked:**
```json
{
  "allowed": false,
  "reason": "Claw is suspended — kill switch active",
  "action_category": "blocked",
  "trust_level_at_decision": "quarantine",
  "approval_required": false,
  "qms_status": "Thank_You_But_No"
}
```

### The 8-Step Governance Pipeline

Every action passes through these checks in order:

1. **Registered?** — Unregistered claws are rejected immediately
2. **Suspended?** — Kill switch check; suspended claws get no further evaluation
3. **Trust level check** — What does this claw's current level allow autonomously?
4. **Manners compliance** — Score below threshold → auto-demote to QUARANTINE
5. **Anomaly detection** — Behavior deviating from baseline → flag for review
6. **Egress whitelist** — External calls blocked unless domain is whitelisted
7. **Approval gate** — Actions requiring human approval are paused here
8. **Audit** — Every decision (allow/gate/block) is written to the cryptographic audit chain

---

## Trust Level Management

### Promote a Claw (One Level at a Time)

```powershell
# Promote from QUARANTINE to PROBATION
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"new_level": "probation", "reason": "Reviewed 10 actions, all appropriate"}' `
  http://localhost:8000/v1/openclaw/claw_abc123def456/promote
```

Valid promotion targets per current level:
- `quarantine` → `probation`
- `probation` → `resident`
- `resident` → `citizen`

### Demote a Claw (Any Lower Level)

```powershell
# Demote from CITIZEN back to PROBATION for suspicious behavior
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"new_level": "probation", "reason": "Unexplained external API calls"}' `
  http://localhost:8000/v1/openclaw/claw_abc123def456/demote
```

### Automatic Demotion (Manners Auto-Demotion)

If a claw's Manners compliance score drops below the configured threshold, TelsonBase automatically demotes it to QUARANTINE without human intervention. This fires at step 4 of the governance pipeline and is audited.

---

## Kill Switch — Suspend and Reinstate

### Suspend a Claw (Instant, No Approval Required)

```powershell
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"reason": "Policy violation — unauthorized data exfiltration attempt"}' `
  http://localhost:8000/v1/openclaw/claw_abc123def456/suspend
```

A suspended claw is rejected at step 2 of every subsequent action request. No further pipeline evaluation occurs.

### Reinstate a Claw

```powershell
curl -s -X POST `
  -H "X-API-Key: $env:MCP_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"reason": "Root cause identified and remediated"}' `
  http://localhost:8000/v1/openclaw/claw_abc123def456/reinstate
```

Reinstated claws return to their trust level at time of suspension.

---

## Monitoring

### List All Claw Instances

```powershell
curl -s -H "X-API-Key: $env:MCP_API_KEY" http://localhost:8000/v1/openclaw/list
```

### Get a Single Instance

```powershell
curl -s -H "X-API-Key: $env:MCP_API_KEY" http://localhost:8000/v1/openclaw/claw_abc123def456
```

### Get Action History

```powershell
curl -s -H "X-API-Key: $env:MCP_API_KEY" "http://localhost:8000/v1/openclaw/claw_abc123def456/actions?limit=50"
```

### Trust Report

Full governance history with promotion/demotion log, Manners score trend, action statistics.

```powershell
curl -s -H "X-API-Key: $env:MCP_API_KEY" http://localhost:8000/v1/openclaw/claw_abc123def456/trust-report
```

---

## Live Test Workflow — Full Governance Cycle

This is the complete test sequence to verify governance is working end-to-end.

**Prerequisites:** Docker stack running, `OPENCLAW_ENABLED=true`, `MCP_API_KEY` set.

```powershell
# Set for convenience
$BASE = "http://localhost:8000"
$KEY = $env:MCP_API_KEY

# Step 1: Enable check — should return list (not 404)
curl -s -H "X-API-Key: $KEY" "$BASE/v1/openclaw/list"

# Step 2: Register a test claw
$reg = curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"name": "test-claw", "api_key": "test-secret-123"}' `
  "$BASE/v1/openclaw/register" | ConvertFrom-Json

$ID = $reg.instance_id
Write-Host "Registered: $ID at trust level: $($reg.trust_level)"

# Step 3: Submit a read action — should be GATED (quarantine blocks everything)
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"tool_name": "read_file", "tool_args": {"path": "/docs/report.txt"}}' `
  "$BASE/v1/openclaw/$ID/action"

# Step 4: Promote to PROBATION
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"new_level": "probation", "reason": "Test promotion"}' `
  "$BASE/v1/openclaw/$ID/promote"

# Step 5: Submit a read action again — should now be ALLOWED at probation
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"tool_name": "read_file", "tool_args": {"path": "/docs/report.txt"}}' `
  "$BASE/v1/openclaw/$ID/action"

# Step 6: Submit an external action — should be GATED at probation
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"tool_name": "http_request", "tool_args": {"url": "https://api.example.com/data"}}' `
  "$BASE/v1/openclaw/$ID/action"

# Step 7: Test the kill switch
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"reason": "Kill switch test"}' `
  "$BASE/v1/openclaw/$ID/suspend"

# Step 8: Submit any action — should be BLOCKED (suspended)
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"tool_name": "read_file", "tool_args": {}}' `
  "$BASE/v1/openclaw/$ID/action"

# Step 9: Check trust report
curl -s -H "X-API-Key: $KEY" "$BASE/v1/openclaw/$ID/trust-report"

# Step 10: Reinstate
curl -s -X POST `
  -H "X-API-Key: $KEY" `
  -H "Content-Type: application/json" `
  -d '{"reason": "Test reinstatement"}' `
  "$BASE/v1/openclaw/$ID/reinstate"
```

**Expected results:**
- Step 3: `allowed: false`, `approval_required: true` (quarantine gates everything)
- Step 5: `allowed: true` (read allowed at probation)
- Step 6: `allowed: false`, `approval_required: true` (external gated at probation)
- Step 8: `allowed: false`, `approval_required: false` (suspended = hard block)

---

## Configuration Reference

In `.env`:

```env
# Master switch — must be true for any OpenClaw feature to work
OPENCLAW_ENABLED=false

# Maximum registered claw instances (default: 100)
OPENCLAW_MAX_INSTANCES=100

# Manners score below which auto-demotion fires (default: 0.5)
OPENCLAW_MANNERS_THRESHOLD=0.5

# Max consecutive blocked actions before auto-suspend (default: 10)
OPENCLAW_MAX_BLOCKED_ACTIONS=10

# Days before inactive claw is flagged for review (default: 30)
OPENCLAW_INACTIVITY_DAYS=30
```

---

## Audit Trail

Every governance decision — allow, gate, block, promote, demote, suspend, reinstate — is written to the cryptographic audit chain. To review OpenClaw audit events:

```powershell
curl -s -H "X-API-Key: $env:MCP_API_KEY" "http://localhost:8000/v1/audit/chain/entries?limit=50" | `
  ConvertFrom-Json | Select-Object -ExpandProperty entries | `
  Where-Object { $_.event_type -like "*openclaw*" }
```

---

*TelsonBase v7.4.0CC — OpenClaw Governance | Quietfire AI*
