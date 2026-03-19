# TB-PROOF-041: How to Add an Agent - Developer Deep Dive

**Sheet ID:** TB-PROOF-041
**Claim Source:** clawcoat.com - Control Your Claw
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- registration, trust transitions, kill switch, manners auto-demotion, and model validator enforcement all covered by test_openclaw.py (55 tests)
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "Every agent starts at Quarantine with zero autonomous permissions. Connecting an agent to TelsonBase takes one API call. Trust is earned from that point forward."

---

## Verdict

VERIFIED - Agent registration is a single authenticated POST to `/v1/openclaw/register`. The system hashes the agent's API key (SHA-256, never stored plaintext), writes the instance to Redis, initializes trust history, and logs the registration to the cryptographic audit chain. Default trust level is QUARANTINE. No agent can start above QUARANTINE without an administrator supplying a substantive written override reason (minimum 10 characters), which is written verbatim to the immutable audit log.

---

## What "Adding an Agent" Actually Means

TelsonBase does not run agents. It **governs** them. When you "add an agent," you are creating a governed identity record for that agent inside TelsonBase. From that moment on, every action the agent attempts is intercepted by the 8-step governance pipeline before execution.

The agent itself is never modified. TelsonBase wraps it.

---

## Two Registration Paths

### Path A - Self-Registration (Agent Registers Itself)

The agent calls the registration endpoint when it first starts up, using its own credentials. It gets back an `instance_id` and a starting trust level of QUARANTINE. It uses that `instance_id` on every subsequent action call.

**When to use:** Agents you control that run on your own infrastructure. Standard deployment pattern.

### Path B - Pre-Registration (Admin Registers the Agent First)

An administrator registers the agent in the dashboard or via API before the agent is deployed. The agent is given a pre-assigned `instance_id` and API key. When the agent starts, it already has a governance record.

**When to use:** Regulated environments where you want the governance record created and audited before the agent ever runs. Legal, healthcare, financial.

Both paths arrive at the same place: QUARANTINE, an `instance_id`, and a full audit entry.

---

## Prerequisites

```bash
# ClawCoat must be running
curl http://localhost:8000/health
# → {"status": "healthy", ...}

# OpenClaw governance must be enabled (.env)
OPENCLAW_ENABLED=true

# You need an admin API key or JWT token
# Get one at: POST /v1/auth/login → access_token
```

---

## Step-by-Step: Path A (Self-Registration)

### Step 1 - The Agent Sends a Registration Request

**Endpoint:** `POST /v1/openclaw/register`
**Auth required:** Yes - admin or `security:write` permission

```python
import httpx

TELSONBASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "your-jwt-token-here"

# The agent's own API key - this gets hashed (SHA-256) before storage.
# ClawCoat never stores the plaintext key.
AGENT_API_KEY = "my-secret-agent-key-abc123"

response = httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/register",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "name": "DocumentProcessor-v1",
        "api_key": AGENT_API_KEY,
        "allowed_tools": ["file_read", "search_files", "database_query"],  # optional whitelist
        "blocked_tools": ["file_delete", "http_request"],                  # optional blacklist
        "metadata": {
            "environment": "production",
            "owner": "ops-team",
            "purpose": "Legal document processing"
        }
        # initial_trust_level omitted → defaults to "quarantine"
    }
)

instance = response.json()
print(instance["instance_id"])      # e.g. "a3f9c1b2e4d67890"
print(instance["trust_level"])      # "quarantine" - always
print(instance["qms_status"])       # "Thank_You"
```

**What happens internally:**

```
register_instance() [core/openclaw.py:366]
  ├── Check active instance count against OPENCLAW_MAX_INSTANCES
  ├── api_key_hash = sha256(api_key)  ← plaintext never stored
  ├── Check for duplicate: if this hash already exists, return existing instance
  ├── Create OpenClawInstance(trust_level=QUARANTINE, manners_score=1.0, ...)
  ├── _persist_instance() → Redis: "openclaw:instance:{instance_id}"
  ├── Initialize trust history: [{old="unregistered", new="quarantine", type="registration"}]
  ├── _persist_trust_history() → Redis: "openclaw:trust_history:{instance_id}"
  └── audit.log(OPENCLAW_REGISTERED, actor=registered_by, ...)
      └── Written to SHA-256 hash-chained audit trail - tamper-evident, permanent
```

### Step 2 - Store the instance_id

The `instance_id` is the agent's governed identity. Every action evaluation call requires it.

```python
INSTANCE_ID = instance["instance_id"]  # store this
```

### Step 3 - Submit Actions for Governance Evaluation

**Endpoint:** `POST /v1/openclaw/{instance_id}/action`

Before executing any action, the agent submits it to TelsonBase. TelsonBase evaluates it and returns a governance decision.

```python
# Agent wants to read a file
action_response = httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/{INSTANCE_ID}/action",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "tool_name": "file_read",
        "tool_args": {"path": "/data/contracts/2026-01-15.pdf"},
        "nonce": "unique-uuid-for-this-call"  # replay protection
    }
)

result = action_response.json()
print(result["allowed"])              # True or False
print(result["approval_required"])    # True = waiting for human
print(result["trust_level_at_decision"])   # "quarantine"
print(result["action_category"])      # "read_internal"
print(result["qms_status"])           # "Thank_You" / "Excuse_Me" / "Thank_You_But_No"
```

**Decision matrix at QUARANTINE (the starting point):**

| Action | Result | Why |
|---|---|---|
| `file_read` | `allowed=False, approval_required=True` | Gated - reads allowed but require HITL approval |
| `file_write` | `allowed=False, approval_required=False` | Blocked entirely at QUARANTINE |
| `http_request` | `allowed=False, approval_required=False` | Blocked at QUARANTINE |
| `file_delete` | `allowed=False, approval_required=False` | Blocked at QUARANTINE |

---

## Step-by-Step: Path B (Pre-Registration with Trust Override)

An admin registers the agent above QUARANTINE. This is the only way to start an agent at a higher trust level. The model validator enforces that a written justification is provided and it goes straight to the audit log.

```python
response = httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/register",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "name": "InternalReportingAgent",
        "api_key": "reporting-agent-key-xyz789",
        "initial_trust_level": "probation",          # starting above quarantine
        "override_reason": "Agent has 90-day production record on staging environment with zero violations. Approved by CTO 2026-02-25.",  # required, min 10 chars, written to audit log verbatim
        "allowed_tools": ["file_read", "database_query", "search_files"],
        "blocked_tools": ["file_delete", "payment_send"],
    }
)
# → instance["trust_level"] == "probation"
# → Full audit trail of the override with the verbatim reason
```

**What the model validator enforces** (`api/openclaw_routes.py:64`):

```python
@model_validator(mode="after")
def validate_trust_override(self) -> "RegisterClawRequest":
    level = (self.initial_trust_level or "quarantine").lower().strip()

    if level not in _TRUST_LADDER:      # must be a valid level
        raise ValueError(...)

    if level != "quarantine":           # override requires justification
        reason = (self.override_reason or "").strip()
        if not reason:
            raise ValueError("override_reason is required ...")
        if len(reason) < 10:            # one-word reasons rejected
            raise ValueError("override_reason must be at least 10 characters ...")
```

**If you skip the override_reason, FastAPI returns a 422 before the handler runs:**

```json
{
  "detail": [{
    "msg": "Value error, override_reason is required when initial_trust_level is 'probation'.
             Provide a substantive justification - it is written verbatim to the audit log.",
    "type": "value_error"
  }]
}
```

---

## The Trust Level Ladder - What Changes as the Agent Earns Trust

```
QUARANTINE ──► PROBATION ──► RESIDENT ──► CITIZEN ──► AGENT
  (all gated)   (reads ok)   (r/w ok)   (autonomous)  (full autonomy)
```

Promotion is always one step at a time. You cannot skip from QUARANTINE to CITIZEN. An admin must explicitly promote.

**Promote an agent one step:**

```python
httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/{INSTANCE_ID}/promote",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "new_level": "probation",    # must be the next level up - no skipping
        "reason": "30 days of clean operation at QUARANTINE. All HITL approvals granted."
    }
)
```

**Demote an agent (instant, skip-capable):**

```python
httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/{INSTANCE_ID}/demote",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "new_level": "quarantine",   # can skip levels - CITIZEN → QUARANTINE in one call
        "reason": "Anomalous behavior detected - credential enumeration pattern."
    }
)
```

---

## Full Permission Matrix by Trust Level

Source: `core/openclaw.py` - `TRUST_PERMISSION_MATRIX`

| Trust Level | Autonomous | Gated (HITL required) | Blocked |
|---|---|---|---|
| **QUARANTINE** | Nothing | READ_INTERNAL | WRITE, DELETE, EXTERNAL, FINANCIAL, SYSTEM |
| **PROBATION** | READ_INTERNAL | WRITE_INTERNAL, EXTERNAL | DELETE, FINANCIAL, SYSTEM |
| **RESIDENT** | READ_INTERNAL, WRITE_INTERNAL | DELETE, EXTERNAL, FINANCIAL, SYSTEM | Nothing |
| **CITIZEN** | All categories | Anomaly-flagged actions only | Nothing |
| **AGENT** | All categories | Nothing (anomalies are advisory) | Nothing |

### Tool-to-Category Map (partial)

```python
# Source: core/openclaw.py - TOOL_CATEGORY_MAP
"file_read"          → READ_INTERNAL
"file_write"         → WRITE_INTERNAL
"edit_file"          → WRITE_INTERNAL
"database_query"     → READ_INTERNAL
"database_insert"    → WRITE_INTERNAL
"file_delete"        → DELETE
"http_request"       → EXTERNAL_REQUEST
"api_call"           → EXTERNAL_REQUEST
"slack_send"         → EXTERNAL_REQUEST
"payment_send"       → FINANCIAL
"invoice_create"     → FINANCIAL
"config_update"      → SYSTEM_CONFIG
"service_restart"    → SYSTEM_CONFIG
# Unknown tools → classified as WRITE_INTERNAL (fail-safe)
```

---

## The 8-Step Governance Pipeline (What Runs on Every Action Call)

Source: `core/openclaw.py` - `evaluate_action()` at line 474

```
Step 1: Instance registered?
   └── get_instance(instance_id) → checks in-memory + Redis fallback
   └── REJECT if unknown: "Instance not registered"

Step 2: Kill switch - is this instance suspended?
   └── Checked BEFORE trust level, BEFORE Manners, BEFORE everything
   └── Redis-backed via is_suspended() - survives restarts
   └── REJECT if suspended: "Instance suspended: {reason}"

Step 3: Nonce replay protection
   └── _check_nonce(nonce) - Redis-backed, TTL-based
   └── REJECT if nonce already seen: "Nonce replay detected"

Step 4: Tool blocklist check
   └── if tool_name in instance.blocked_tools → REJECT
   └── if instance.allowed_tools and tool_name not in allowed_tools → REJECT

Step 5: Classify action category
   └── TOOL_CATEGORY_MAP.get(tool_name, ActionCategory.WRITE_INTERNAL)
   └── Unknown tools default to WRITE_INTERNAL (safe default)

Step 6: Manners compliance auto-demotion
   └── if instance.manners_score < OPENCLAW_AUTO_DEMOTE_THRESHOLD:
   └──   Instantly demote to QUARANTINE, log TrustChangeRecord
   └──   The degraded trust level is used for this action and all following actions

Step 7: Trust level permission check
   └── TRUST_PERMISSION_MATRIX[trust_level][category]
   └── "blocked" → REJECT immediately
   └── "gated"   → allowed=False, approval_required=True → enters HITL queue
   └── "autonomous" → proceed to Step 8

Step 8: Anomaly detection
   └── _check_anomaly(instance_id, tool_name, tool_args)
   └── Flags: rate spikes, capability probing, enumeration patterns
   └── CITIZEN tier: anomaly → approval_required=True (gated)
   └── AGENT tier: anomaly → advisory log only, not blocking

→ Audit every decision to cryptographic hash chain
→ Update instance counters (action_count, actions_allowed, actions_blocked, actions_gated)
→ Persist updated instance state to Redis
```

---

## Response Interpretation

Every action evaluation returns:

```json
{
  "allowed": true,
  "reason": "Action permitted at trust level 'resident'",
  "action_category": "read_internal",
  "trust_level_at_decision": "resident",
  "approval_required": false,
  "approval_id": null,
  "manners_score_at_decision": 0.95,
  "anomaly_flagged": false,
  "qms_status": "Thank_You"
}
```

| `qms_status` value | Meaning |
|---|---|
| `Thank_You` | Action allowed - proceed |
| `Excuse_Me` | Action gated - waiting for human approval |
| `Thank_You_But_No` | Action blocked - do not proceed |

When `approval_required=true`, the `approval_id` is returned. Poll `GET /v1/approvals/{approval_id}` for the human decision.

---

## Instant Suspend - The Kill Switch

One call. Zero grace period. All subsequent actions from this instance return blocked regardless of trust level.

```python
httpx.post(
    f"{TELSONBASE_URL}/v1/openclaw/{INSTANCE_ID}/suspend",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={"reason": "Credential enumeration behavior detected - suspended pending review."}
)
# → {"suspended": true, "qms_status": "Thank_You"}
```

Kill switch check is Step 2 of the pipeline - before trust levels, before Manners, before nonce. Only a human administrator can reinstate a suspended agent.

---

## Dashboard Registration (No-Code Path)

If you prefer a UI instead of the API:

1. Log in to `http://localhost:8000/dashboard`
2. Navigate to the **OpenClaw** tab
3. Click **Register New Instance**
4. Fill in: Name, API Key, Allowed/Blocked tools (optional), Starting Trust Level
5. If starting above QUARANTINE, provide override reason
6. Submit → instance appears in the governed instance list immediately

The dashboard calls the same `/v1/openclaw/register` endpoint under the hood. Same audit trail. Same rules.

---

## Source Files

| File | Purpose |
|---|---|
| `core/openclaw.py` | Full governance engine - TrustLevel enum, VALID_PROMOTIONS, VALID_DEMOTIONS, TRUST_PERMISSION_MATRIX, TOOL_CATEGORY_MAP, OpenClawInstance model, register_instance(), evaluate_action() |
| `api/openclaw_routes.py` | REST API layer - RegisterClawRequest with model_validator, POST /register, POST /{id}/action, POST /{id}/promote, POST /{id}/demote, POST /{id}/suspend |
| `tests/test_openclaw.py` | 55 tests covering registration, trust transitions, pipeline steps, kill switch, Manners auto-demotion, anomaly detection |

---

## Verification Commands

```bash
# Confirm registration endpoint exists and requires auth
curl -s http://localhost:8000/v1/openclaw/register -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"test","api_key":"test"}' | python3 -m json.tool
# → 401 Unauthorized (correct - auth required)

# Register an agent and confirm QUARANTINE start
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-agent","api_key":"test-key-001"}' | python3 -m json.tool
# → {"trust_level": "quarantine", "qms_status": "Thank_You", ...}

# Confirm override_reason required for non-quarantine start
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","api_key":"test-key-002","initial_trust_level":"probation"}' | python3 -m json.tool
# → 422 Unprocessable Entity: override_reason is required ...

# Run the full OpenClaw test suite
docker compose exec mcp_server python -m pytest tests/test_openclaw.py -v --tb=short
# → 55 passed
```

---

## Skeptic Follow-Ups

**"Can the agent promote its own trust level?"**
No. The `POST /{id}/promote` endpoint requires `security:write` permission - the same permission level as an administrator. The agent's own API key does not have this permission. An agent cannot elevate itself. Source: `api/openclaw_routes.py` - `promote_claw()` calls `require_permission("security:write")`.

**"What if the agent lies about its instance_id?"**
It gets a 404-equivalent governance rejection: "Instance not registered." The registration records the SHA-256 hash of the API key. The governance pipeline does not accept an `instance_id` without a matching registered record. There is no path to a valid governance decision without being registered.

**"What happens if TelsonBase goes down and comes back up?"**
All instance state is persisted to Redis at every write. On startup, `_load_from_redis()` restores all instances, trust levels, trust history, and the suspended IDs set. A suspended agent remains suspended after restart. Source: `core/openclaw.py` - `_load_from_redis()`.

**"What if the agent sends the same nonce twice (replay attack)?"**
Step 3 of the pipeline. Nonces are stored in Redis with a TTL. If the nonce has been seen, the action is rejected immediately: "Nonce replay detected." The instance counters are not updated on replay rejection (replay attempts are not counted as agent actions). Source: `core/openclaw.py` - `_check_nonce()`, `_mark_nonce_used()`.

**"Does registering above QUARANTINE bypass the audit trail?"**
No. Registration with a trust override uses `promote_trust()` called once per step from QUARANTINE to the target level. Each step produces its own `TrustChangeRecord` and audit log entry. The override reason is written verbatim to every entry. An auditor can see every step that was taken and why. Source: `api/openclaw_routes.py:257-268`.

**"What stops someone from registering 1,000 agents?"**
`OPENCLAW_MAX_INSTANCES` - configured in `.env`, checked on every registration attempt. If the active instance count is at or above the limit, `register_instance()` returns `None` and the endpoint returns a 400. Source: `core/openclaw.py:382-388`.

---

## Related Proof Sheets

| Sheet | Covers |
|---|---|
| [TB-PROOF-035](TB-PROOF-035_openclaw_governance.md) | OpenClaw Governance Pipeline (overview) |
| [TB-PROOF-036](TB-PROOF-036_trust_level_matrix.md) | Full Trust Level Permission Matrix |
| [TB-PROOF-037](TB-PROOF-037_openclaw_kill_switch.md) | Kill Switch - instant suspension |
| [TB-PROOF-038](TB-PROOF-038_manners_auto_demotion.md) | Manners Auto-Demotion |
| [TB-PROOF-039](TB-PROOF-039_earned_trust_model.md) | Earned Trust Model |
| [TB-PROOF-019](TB-PROOF-019_hitl_approval_gates.md) | Human-in-the-Loop Approval Gates |

---

*Sheet TB-PROOF-041 | ClawCoat v11.0.2 | March 19, 2026*
