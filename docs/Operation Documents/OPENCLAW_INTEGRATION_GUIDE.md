# ClawCoat - OpenClaw Integration Guide

**Version:** v11.0.2 · **Maintainer:** Quietfire AI

---

## Why OpenClaw, and Why This Guide

OpenClaw is ClawCoat's first verified agent integration. It was chosen because of its
widespread deployment - security researchers have found over 135,000 exposed instances in
the wild - which makes it the highest-priority framework to govern. CVE-2026-25253 (RCE via
malicious WebSocket link) was rated critical. The ClawHub skill registry was found to contain
malware distributed at scale. The risk profile is real and well-documented.

ClawCoat wraps OpenClaw with a guiding layer. Every action your claw wants to take -
read a file, call an API, modify a document - is evaluated through the 8-step pipeline before
execution. Nothing runs without a decision. Every decision is written to a cryptographic audit
chain. You stay in control.

This is not about slowing OpenClaw down. It is about knowing what it is doing and having the
power to stop it.

OpenClaw is the first integration. Others are coming - see [Agent Framework Ecosystem](#agent-framework-ecosystem) at the end of this guide.

---

## What You Are Building

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Environment                       │
│                                                             │
│   ┌──────────────┐          ┌─────────────────────────┐    │
│   │   OpenClaw   │  ──────► │      ClawCoat         │    │
│   │   Instance   │  action? │   Governance Engine     │    │
│   │              │  ◄────── │   (8-step pipeline)     │    │
│   │              │  allow / │                         │    │
│   │              │  gate /  │  ✓ Trust level check    │    │
│   │              │  block   │  ✓ Manners compliance   │    │
│   └──────────────┘          │  ✓ Anomaly detection    │    │
│                             │  ✓ Egress whitelist     │    │
│                             │  ✓ HITL approval gate   │    │
│                             │  ✓ Cryptographic audit  │    │
│                             └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**How it works in plain English:**
- OpenClaw wants to take an action
- Your workflow calls ClawCoat's API with the action details
- ClawCoat evaluates it through the pipeline and returns: `allowed`, `gated`, or `blocked`
- If **allowed** → OpenClaw executes
- If **gated** → OpenClaw waits; you approve or deny in the ClawCoat dashboard
- If **blocked** → OpenClaw does not execute; the incident is audited

ClawCoat does not modify OpenClaw's code. You are in control of when governance fires.

---

## Prerequisites Checklist

Before starting, verify each of these:

- [ ] **An AI agent installed and running** - This guide uses OpenClaw as the reference implementation. See Part 1 below for setup.
- [ ] **ClawCoat running** - `docker compose ps` shows all services healthy, API at `http://localhost:8000`
- [ ] **ClawCoat API key** - found in your `.env` file as `MCP_API_KEY=...`
- [ ] **curl installed** - for the API calls in this guide (Windows: included in Windows 10+ and 11)
- [ ] **ClawCoat dashboard accessible** - `http://localhost:8000/dashboard`

---

## Part 1: Install Your AI Agent

ClawCoat is a guiding layer - it does not care what agent sits behind it. This guide uses **OpenClaw** as the reference implementation because it is what ClawCoat was built and tested against first. If you are integrating a different compatible agent, the ClawCoat API steps in Parts 4-7 apply regardless of which agent you use.

### Install OpenClaw

OpenClaw maintains their own installation documentation. Follow their official guide:

> **[→ OpenClaw Installation Documentation](https://docs.openclaw.ai/install#install)**

Their guide covers installation on Windows, macOS, Linux, and WSL2.

**Before continuing:** Confirm your OpenClaw instance is installed and running per their documentation. Also verify it is not exposed on your local network before connecting to any external governance layer - consult OpenClaw's security hardening documentation for local binding configuration.

**You are now ready to connect ClawCoat governance.**

---

## Part 2: Deploy ClawCoat

If ClawCoat is already running, skip to Part 3.

If you are starting fresh, follow the full deployment guide:

```
docs/Operation Documents/DEPLOYMENT_GUIDE.md
```

Quick check that it is running:

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", ...}

curl -H "X-API-Key: $(cat secrets/telsonbase_mcp_api_key)" http://localhost:8000/v1/system/status
# Expected: 200 with system status JSON
```

---

## Part 3: Enable OpenClaw Governance in ClawCoat

> **Terminal reminder - use Command Prompt (CMD) for Parts 3 and 4, not PowerShell.**
> In PowerShell, `curl` is an alias for a different command (`Invoke-WebRequest`) and the
> syntax is completely incompatible. The commands below use real `curl.exe`, which is
> built into Windows and works correctly from CMD. If you open PowerShell by mistake,
> close it and open Command Prompt instead: press the Windows key, type `cmd`, right-click
> **Command Prompt**, click **Run as administrator**.

OpenClaw governance is feature-flagged off by default. You turn it on explicitly.

### 3a. Edit Your .env File

Open `C:\Claude_Code\ClawCoat\.env` and find this line:

```env
OPENCLAW_ENABLED=false
```

Change it to:

```env
OPENCLAW_ENABLED=true
```

Optional: Review the other OpenClaw settings while you are here:

```env
# Maximum registered claw instances (default: 100)
OPENCLAW_MAX_INSTANCES=100

# Manners compliance score below which auto-demotion fires (default: 0.5)
# Score of 1.0 = perfect. Score drops with each governance violation.
OPENCLAW_MANNERS_THRESHOLD=0.5

# Consecutive blocked actions before auto-suspend (default: 10)
OPENCLAW_MAX_BLOCKED_ACTIONS=10
```

### 3b. Rebuild and Restart

Open **PowerShell** and navigate to your ClawCoat directory:

```powershell
cd C:\Claude_Code\ClawCoat
```

Run these **one at a time**:

```powershell
docker compose build mcp_server
```

Docker will print output as it rebuilds - wait for it to finish. You should see `Successfully built` or a similar completion message at the end.

```powershell
docker compose up -d mcp_server worker beat
```

You should see `Started` or `Recreated` next to each service name.

Wait about 15 seconds for the services to come up, then confirm governance is live:

Open **Command Prompt** and run these **two commands in order** - the first stores your
API key in a variable so the second line stays short enough to not wrap:

```cmd
set API_KEY=YOUR_KEY_HERE
```

```cmd
curl -s -H "X-API-Key: %API_KEY%" http://localhost:8000/v1/openclaw/list
```

Replace `YOUR_KEY_HERE` with the value of `MCP_API_KEY` from your `.env` file.
The `set` line will be long - that is normal and expected.

**Expected response:**
```json
[]
```

An empty array means governance is live with no claws registered yet - exactly right at this stage.

If you get `{"detail":"OpenClaw governance is not enabled..."}`, check that `.env` has `OPENCLAW_ENABLED=true` and rebuild the container. Check that `.env` was saved and
the container was rebuilt, not just restarted.

**Verify in logs:**
```powershell
docker compose logs mcp_server | grep -i openclaw
# Should see: "OpenClaw governance engine initialized"
```

---

## Part 4: Register Your OpenClaw Instance

Every OpenClaw instance that ClawCoat will govern must be registered. Registration is what
gives the claw its identity, starting trust level, and audit trail.

### 4a. Register the Instance

Open **PowerShell** and navigate to your ClawCoat directory first:

```powershell
cd C:\Claude_Code\ClawCoat
```

Then paste this entire block at once - it reads your API key, builds the registration request, and prints the result:

```powershell
# Windows PowerShell
$API_KEY = Get-Content secrets/telsonbase_mcp_api_key

$body = @{
    name         = "my-first-claw"
    api_key      = "claw-secret-key-here"
    allowed_tools = @()
    blocked_tools = @()
} | ConvertTo-Json

$response = Invoke-WebRequest `
    -Uri "http://localhost:8000/v1/openclaw/register" `
    -Method POST `
    -Headers @{"X-API-Key" = $API_KEY; "Content-Type" = "application/json"} `
    -Body $body | ConvertFrom-Json

$response
$CLAW_ID = $response.instance_id
Write-Host "Claw registered: $CLAW_ID"
```

You should see a JSON block with `instance_id`, `trust_level: "quarantine"`, and `suspended: false`. The line `Claw registered: claw_...` at the end confirms the ID was captured. **Save that ID** - you will need it for every step that follows.

```bash
# Linux / macOS / WSL / AWS
API_KEY=$(cat secrets/telsonbase_mcp_api_key)

CLAW_ID=$(curl -s -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-first-claw", "api_key": "claw-secret-key-here", "allowed_tools": [], "blocked_tools": []}' \
  http://localhost:8000/v1/openclaw/register | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])")

echo "Claw registered: $CLAW_ID"
```

**Expected response:**
```json
{
  "instance_id": "8abb00d954a44fd4",
  "name": "my-first-claw",
  "trust_level": "quarantine",
  "manners_score": 1.0,
  "action_count": 0,
  "actions_allowed": 0,
  "actions_blocked": 0,
  "actions_gated": 0,
  "suspended": false,
  "registered_at": "2026-02-22T22:11:19.477900+00:00",
  "last_action_at": null,
  "qms_status": "Thank_You"
}
```

**Save the `instance_id`.** You need it for every subsequent call.

### 4b. Verify Registration in the Dashboard

1. Open `http://localhost:8000/dashboard` in your browser
2. Navigate to the **OpenClaw** tab
3. You should see `my-first-claw` listed with trust level **QUARANTINE**

---

## Part 5: Your First Governed Action

This is the core integration. Before OpenClaw executes any action, your workflow calls
ClawCoat to get a governance decision.

> **Windows CMD note:** The commands below use `%API_KEY%` and `%CLAW_ID%` (CMD variable
> syntax). Make sure both variables are set - you set `API_KEY` in Part 3b and should set
> `CLAW_ID` now if you have not already:
> ```cmd
> set CLAW_ID=YOUR_INSTANCE_ID_HERE
> ```
> Replace `YOUR_INSTANCE_ID_HERE` with the `instance_id` from your registration response.
>
> **Inline JSON tip for CMD:** Long curl commands with inline JSON can break when pasted
> because CMD treats each line as a separate command. To avoid this, write the payload to
> a file first and use `-d @filename.json`. Examples below show both methods.

### 5a. Submit a Read Action (Expect: GATED)

At QUARANTINE trust level, every action requires approval - even a simple file read.

**Windows CMD - payload file method (recommended):**
```cmd
echo {"tool_name":"read_file","tool_args":{"path":"/documents/report.txt"}} > payload_read.json
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_read.json http://localhost:8000/v1/openclaw/%CLAW_ID%/action
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/documents/report.txt"}}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/action
```

**Expected response:**
```json
{
  "allowed": false,
  "reason": "Action requires human approval",
  "action_category": "read_internal",
  "trust_level_at_decision": "quarantine",
  "approval_required": true,
  "approval_id": "APPR-0D2DB72102D0",
  "manners_score_at_decision": 1.0,
  "anomaly_flagged": false,
  "qms_status": "Excuse_Me"
}
```

**What this means:** ClawCoat returned `allowed: false` and created a real approval request
in the system (`APPR-` prefix = stored in the approval manager, visible in the dashboard).
The claw does not execute. A human must approve or deny.

### 5b. See the Approval Request in the Dashboard

1. Go to `http://localhost:8000/dashboard`
2. Navigate to the **Approvals** tab
3. You will see the pending approval: **URGENT** badge, the `APPR-` ID, action name
   `read_file`, description "OpenClaw my-first-claw (quarantine) wants to: read_file",
   and the full payload (tool name, path, instance ID)
4. Click **Approve** or **Reject**

The Approvals tab badge shows a count of pending requests. The OpenClaw tab shows a count
of registered instances.

### 5c. Submit an External Action (Expect: BLOCKED)

External calls at QUARANTINE are hard-blocked - no approval created, just denied.

**Windows CMD:**
```cmd
echo {"tool_name":"http_request","tool_args":{"url":"https://api.example.com/data"}} > payload_external.json
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_external.json http://localhost:8000/v1/openclaw/%CLAW_ID%/action
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"tool_name": "http_request", "tool_args": {"url": "https://api.example.com/data"}}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/action
```

**Expected response:**
```json
{
  "allowed": false,
  "reason": "Action category 'external_request' blocked at trust level 'quarantine'",
  "action_category": "external_request",
  "approval_required": false,
  "qms_status": "Thank_You_But_No"
}
```

**What this means:** External calls are blocked outright at QUARANTINE - no approval
offered, just denied. Note `approval_required: false` - this is different from the read
action above which returned `approval_required: true`. A new, unverified claw has no
business calling external APIs.

---

## Part 6: The Trust Journey

Trust is earned through demonstrated behavior. You promote the claw manually after reviewing
its action history and deciding it has earned more autonomy.

### The Five Trust Levels

| Level | What the Claw Can Do Autonomously | What Requires Approval | What Is Blocked |
|---|---|---|---|
| **QUARANTINE** | Nothing | Every action | External calls |
| **PROBATION** | Internal reads | External calls, high-risk writes | Destructive actions |
| **RESIDENT** | Most internal operations | High-risk, destructive | - |
| **CITIZEN** | Almost everything | Anomaly-flagged actions only | - |
| **AGENT** | Full autonomy (300 actions/min) | Nothing | Nothing |

AGENT is the apex designation. It requires a 99.9% success rate, zero anomaly tolerance, and
re-verification every 3 days. Promotion is sequential - a claw cannot skip from QUARANTINE to
CITIZEN. Demotion can skip levels instantly.

### 6a. Promote to PROBATION

After reviewing the claw's first few requests and confirming they were appropriate:

**Windows CMD:**
```cmd
echo {"new_level":"probation","reason":"Reviewed first actions - all appropriate"} > payload_promote.json
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_promote.json http://localhost:8000/v1/openclaw/%CLAW_ID%/promote
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"new_level": "probation", "reason": "Reviewed first 5 actions - all appropriate file reads"}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/promote
```

**Expected response:**
```json
{
  "instance_id": "8abb00d954a44fd4",
  "new_trust_level": "probation",
  "promoted_by": "system:master",
  "qms_status": "Thank_You"
}
```

### 6b. Test PROBATION Behavior

Submit the same read action from Step 5a:

**Windows CMD:**
```cmd
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_read.json http://localhost:8000/v1/openclaw/%CLAW_ID%/action
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/documents/report.txt"}}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/action
```

**Expected response:**
```json
{
  "allowed": true,
  "reason": "Action permitted at current trust level",
  "action_category": "read_internal",
  "trust_level_at_decision": "probation",
  "approval_required": false,
  "qms_status": "Thank_You"
}
```

The read is now **allowed without human approval**. The claw has earned that.

Submit the external call again - it should still be gated (approval required, not hard blocked):

**Windows CMD:**
```cmd
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_external.json http://localhost:8000/v1/openclaw/%CLAW_ID%/action
```

**Expected response:**
```json
{
  "allowed": false,
  "reason": "Action requires human approval",
  "action_category": "external_request",
  "trust_level_at_decision": "probation",
  "approval_required": true,
  "qms_status": "Excuse_Me"
}
```

External calls still require human review at PROBATION. Note the difference from QUARANTINE:
at QUARANTINE external calls were hard-blocked (`approval_required: false`); at PROBATION
they are gated (`approval_required: true`) - a step up in earned trust.

### 6c. Promote to RESIDENT

After the claw has built a clean record at PROBATION:

**Windows CMD:**
```cmd
echo {"new_level":"resident","reason":"30-day review complete - consistent behavior"} > payload_promote_resident.json
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_promote_resident.json http://localhost:8000/v1/openclaw/%CLAW_ID%/promote
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"new_level": "resident", "reason": "30-day review complete - consistent, appropriate behavior"}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/promote
```

At RESIDENT, internal reads and most writes are autonomous. External calls with whitelisted
domains are permitted. Only high-risk or destructive operations require approval.

### 6d. The Kill Switch - Use It Without Hesitation

If you ever see behavior that concerns you, suspend the claw immediately. No approval
required. Takes effect on the next action.

**Windows CMD:**
```cmd
set URL=http://localhost:8000/v1/openclaw/%CLAW_ID%/suspend
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_suspend.json %URL%
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reason": "Unexplained external API calls at 2am - investigating"}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/suspend
```

The claw is now hard-blocked. Every subsequent action returns:
```json
{"allowed": false, "reason": "Instance suspended: Testing kill switch", "trust_level_at_decision": "probation", "approval_required": false, "qms_status": "Thank_You_But_No"}
```

To reinstate after investigation:

**Windows CMD:**
```cmd
set URL=http://localhost:8000/v1/openclaw/%CLAW_ID%/reinstate
curl -s -X POST -H "X-API-Key: %API_KEY%" -H "Content-Type: application/json" -d @payload_reinstate.json %URL%
```

**Linux / macOS / WSL:**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reason": "Root cause identified - misconfigured external trigger. Remediated."}' \
  http://localhost:8000/v1/openclaw/$CLAW_ID/reinstate
```

---

## Part 7: Monitor Your Governed Claw

### 7a. Check the Trust Report

Full history: every promotion, every demotion, every Manners score change, action statistics.

**Windows CMD:**
```cmd
set URL=http://localhost:8000/v1/openclaw/%CLAW_ID%/trust-report
curl -s -H "X-API-Key: %API_KEY%" %URL%
```

**Linux / macOS / WSL:**
```bash
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/v1/openclaw/$CLAW_ID/trust-report
```

### 7b. Check Action History

**Windows CMD:**
```cmd
set URL=http://localhost:8000/v1/openclaw/%CLAW_ID%/actions?limit=50
curl -s -H "X-API-Key: %API_KEY%" %URL%
```

**Linux / macOS / WSL:**
```bash
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8000/v1/openclaw/$CLAW_ID/actions?limit=50"
```

### 7c. Audit Trail - Every Decision Is Permanently Recorded

Every governance decision is written to ClawCoat's cryptographic audit chain. The chain is
SHA-256 hash-linked - any tampering breaks the chain and is detectable.

**Windows CMD** - view raw audit entries (look for `openclaw.` event types):
```cmd
set URL=http://localhost:8000/v1/audit/chain/entries?limit=50
curl -s -H "X-API-Key: %API_KEY%" %URL%
```

The response will be a JSON array of audit entries. Look for entries where `event_type`
starts with `openclaw.` - these are the governance decisions for your claw.

**Linux / macOS / WSL** - filter to OpenClaw events only:
```bash
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/v1/audit/chain/entries?limit=50" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for e in data.get('entries', []):
    if 'openclaw' in e.get('event_type', ''):
        print(e['event_type'], '|', e.get('details', {}).get('instance_id',''), '|', e['timestamp'])
"
```

### 7d. Dashboard Verification

Open `http://localhost:8000/dashboard` and confirm you can see:

- [ ] **OpenClaw tab** - your claw instance(s) with current trust level, action counts, Manners score, and the Trust Level Governance Matrix
- [ ] **Approvals tab** - pending action requests (badge count shows how many are waiting)
- [ ] **Audit Trail tab** - `openclaw.*` events in the audit log with hash chain intact
- [ ] **Anomalies tab** - should be empty for a well-behaved claw

---

## Part 8: Production Notes

### Automate the Governance Check in Your OpenClaw Workflow

The current integration pattern is: your OpenClaw workflow calls ClawCoat before executing
each action. Here is the pattern in pseudocode:

```python
def governed_action(tool_name, tool_args):
    # Step 1: Ask ClawCoat for a governance decision
    response = requests.post(
        f"http://localhost:8000/v1/openclaw/{CLAW_ID}/action",
        headers={"X-API-Key": API_KEY},
        json={"tool_name": tool_name, "tool_args": tool_args}
    )
    decision = response.json()

    # Step 2: Act on the decision
    if decision["allowed"]:
        return execute_action(tool_name, tool_args)

    elif decision.get("approval_required"):
        # Action is gated - wait for human decision in ClawCoat dashboard
        # Poll /v1/approvals/{approval_id} or subscribe to webhook
        return wait_for_approval(decision["approval_id"])

    else:
        # Hard block - do not execute
        log_blocked_action(tool_name, tool_args, decision["reason"])
        return None
```

### What Gets Flagged Automatically

You do not have to configure rules for every scenario. ClawCoat's governance pipeline
handles these automatically based on trust level:

| Tool Category | Examples | QUARANTINE | PROBATION | RESIDENT | CITIZEN |
|---|---|---|---|---|---|
| Internal read | read_file, list_dir | GATE | ALLOW | ALLOW | ALLOW |
| Internal write | write_file, create_dir | GATE | GATE | ALLOW | ALLOW |
| External call | http_request, api_call | BLOCK | GATE | GATE* | ALLOW* |
| Destructive | delete_file, rm_dir | BLOCK | BLOCK | GATE | GATE |

*External calls at RESIDENT and CITIZEN require the domain to be on ClawCoat's egress whitelist.

### Egress Whitelist - Approved External Domains

To allow external calls at RESIDENT or CITIZEN, add domains to the whitelist:

```bash
curl -s -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain": "api.example.com", "reason": "Required for CRM integration"}' \
  http://localhost:8000/v1/toolroom/sources/add
```

Requires HITL approval - a human must confirm before any external domain is whitelisted.

### Manners Compliance - Automatic Demotion

ClawCoat tracks a Manners compliance score for every claw (1.0 = perfect, 0.0 = suspended).
The score decreases each time a claw attempts blocked actions repeatedly, triggers anomaly
detection, or has an approval denied by a human reviewer.

The `OPENCLAW_MANNERS_THRESHOLD` setting (default: 0.5) controls when ClawCoat automatically
demotes a claw. No human action required. The event is audited. The system also hard-quarantines
any agent - regardless of score - that triggers three or more violations within a 24-hour window.

For the full Manners scoring model and violation severity table, see
`docs/Compliance Documents/MANNERS_COMPLIANCE.md`.

---

## Quick Reference Card

```
Register a claw:    POST /v1/openclaw/register
Submit an action:   POST /v1/openclaw/{id}/action
Promote trust:      POST /v1/openclaw/{id}/promote
Demote trust:       POST /v1/openclaw/{id}/demote
Suspend (kill):     POST /v1/openclaw/{id}/suspend
Reinstate:          POST /v1/openclaw/{id}/reinstate
List all claws:     GET  /v1/openclaw/list
Get one claw:       GET  /v1/openclaw/{id}
Action history:     GET  /v1/openclaw/{id}/actions
Trust report:       GET  /v1/openclaw/{id}/trust-report
```

**Trust levels:** QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT (one step at a time, up)
**Demotion:** Any level, any time, instant
**Kill switch:** Immediate hard block, survives restarts (Redis-persisted)

---

## Troubleshooting

**`/v1/openclaw/list` returns 404**
→ `OPENCLAW_ENABLED=false` in `.env`. Flip to `true` and rebuild: `docker compose build mcp_server && docker compose up -d mcp_server`

**Registration succeeds but claw does not appear in dashboard**
→ Hard-refresh the dashboard. The OpenClaw tab may be cached.

**Promoted to PROBATION but reads are still gated**
→ Check the trust level on the claw: `GET /v1/openclaw/{id}`. If it shows QUARANTINE, the promotion may have been rejected by an approval rule.

**Kill switch reinstated but claw is still blocked**
→ Confirm with `GET /v1/openclaw/{id}` that `suspended: false`. If still true, a second suspend may have fired (Manners threshold). Check action history.

**Approval request created but not visible in dashboard**
→ Go to the Approvals tab and check the filter - it may default to "my approvals" only. Switch to "all pending."

---

## Agent Framework Ecosystem

### OpenClaw is the First. Others Are Coming.

ClawCoat's governance pipeline is framework-agnostic. The `POST /v1/openclaw/{id}/action`
endpoint evaluates any action from any agent - OpenClaw was integrated first because of its
deployment scale and documented risk profile, not because it is the only option.

Future releases will add verified integrations for other AI agent frameworks. Each integration
goes through testing by Quietfire AI and community validation before being listed as supported.
Testing covers the full governance pipeline: trust level enforcement, Manners scoring, kill
switch behavior, HITL gate flow, and audit chain integrity.

### Proposing a Framework for Integration

If you are working with an agent framework you would like to see integrated:

1. **Open a GitHub Discussion** in the `QuietFireAI/ClawCoat` repository under the
   `agent-integrations` category. Describe the framework, its deployment scale, and the
   governance risks it presents.

2. **Contribute a proof of integration** - if you have already connected a framework to
   ClawCoat's governance API, share the integration pattern. A working example accelerates
   the process significantly.

3. **Community testing** - proposed integrations that pass community testing against the
   governance smoke test (`scripts/governance_smoke_test.sh`) are prioritized for official
   inclusion.

See `CONTRIBUTING.md` for the full contribution process.

---

*ClawCoat v11.0.2 · Quietfire AI · March 19, 2026*
*Questions: support@clawcoat.com*
