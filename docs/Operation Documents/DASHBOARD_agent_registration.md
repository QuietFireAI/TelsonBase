# Adding Your First Agent - Dashboard Walkthrough

**Version:** v11.0.2 · **Maintainer:** Quietfire AI
**Prerequisite:** ClawCoat is running. Docker Desktop is open. You have your API key.

---

## Before You Start

Two things you need in hand:

1. **Your platform API key** - the key generated when you ran `generate_secrets.sh`. Find it any time by running this in **Git Bash** from the ClawCoat directory:
   ```bash
   cat secrets/telsonbase_mcp_api_key
   ```

2. **The dashboard open** - `http://localhost:8000/dashboard`

---

## Step 1 - Connect the Dashboard

The dashboard loads in **Offline** mode by default. Nothing works until you connect it to the backend.

1. Look at the top-right of the dashboard header - it will show **Offline** with a grey dot
2. Click **Offline** - the Connection panel slides in
3. Paste your platform API key into the field
4. Click **Connect**
5. The header switches to **Live** with a green health dot

You're now talking to the backend. Every action you take from here is real and audited.

---

## Step 2 - Register Your Agent

1. Click the **Agents** tab in the dashboard navigation
2. Click **Register Agent** (button at the top-right of the tab)
  - If no agents exist yet, there is also a button in the empty state - same modal, same result

**Fill in the five fields:**

| Field | What to enter |
|---|---|
| **Agent Type** | OpenClaw - gives you the full 8-step governance pipeline |
| **Agent Name** | Whatever you want to call this agent. Shows up in audit logs exactly as typed. |
| **API Key** | Your platform API key (same one you used to connect the dashboard) |
| **Starting Trust Level** | Leave at **QUARANTINE** - this is correct and intentional |
| **Trust Override Justification** | Leave blank (only required if you picked a level above Quarantine) |

3. Click **Submit**

> **About the API Key field:** ClawCoat uses the platform API key as the agent's credential because all governance calls run through the same authenticated API. Each agent is tracked by its unique `instance_id`, not by a separate key - so the same platform key works for every agent you register. Agent 1 and Agent 2 both use the same key but have completely separate trust levels, Manners scores, action histories, and kill switches.

---

## Step 3 - Confirm Registration

After submit, switch to the **OpenClaw** tab.

Your agent appears on a card showing:
- **Name:** what you entered
- **Trust Level:** QUARANTINE
- **Instance ID:** a unique identifier like `a1b2c3d4e5f60789` - copy this, you'll need it

The agent is registered. It is fully locked down at QUARANTINE - no autonomous action is permitted yet. That's the correct starting state.

---

## Step 4 - Promote from QUARANTINE

An agent at QUARANTINE cannot do useful work. Promote it one level to PROBATION so it can begin operating.

**From the dashboard (OpenClaw tab):**
1. Find your agent card
2. Click **Promote**
3. Enter a brief reason: `Initial setup, reviewed and approved`
4. Trust level updates to **PROBATION**

**Or from Git Bash** (run these from the ClawCoat directory):

First, set your API key as a variable so you don't have to paste it repeatedly:
```bash
API_KEY=$(cat secrets/telsonbase_mcp_api_key)
```

Then promote - replace `YOUR_INSTANCE_ID` with the ID from the OpenClaw tab:
```bash
curl -X POST http://localhost:8000/v1/openclaw/YOUR_INSTANCE_ID/promote \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"new_level": "probation", "reason": "Initial setup, reviewed and approved"}'
```

**At PROBATION your agent can:**
- ✓ Internal read operations - allowed, no approval needed
- ✗ External API calls - gated, queued for human approval
- ✗ Destructive operations - blocked

---

## Step 5 - Verify the Loop

Open **Git Bash** from the ClawCoat directory. If you have not set your API key variable yet, do it now:

```bash
API_KEY=$(cat secrets/telsonbase_mcp_api_key)
```

Replace `YOUR_INSTANCE_ID` with the ID shown on the agent card in the OpenClaw tab.

**Test 1 - Read action (should be allowed at PROBATION):**
```bash
curl -X POST http://localhost:8000/v1/openclaw/YOUR_INSTANCE_ID/action \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/docs/report.txt"}}'
```

**Expected response:**
```json
{
  "allowed": true,
  "reason": "Action permitted at PROBATION trust level",
  "action_category": "read",
  "trust_level_at_decision": "probation",
  "approval_required": false,
  "manners_score_at_decision": 1.0,
  "qms_status": "Thank_You"
}
```

**Test 2 - External call (should be gated - held for your review, not blocked):**
```bash
curl -X POST http://localhost:8000/v1/openclaw/YOUR_INSTANCE_ID/action \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "http_post", "tool_args": {"url": "https://api.example.com/data"}}'
```

**Expected response (PROBATION, external action):**
```json
{
  "allowed": false,
  "reason": "External action requires approval at PROBATION trust level",
  "approval_required": true,
  "approval_id": "appr_xyz789",
  "qms_status": "Excuse_Me"
}
```

That approval now sits in the **Approvals** tab waiting for your review. The agent cannot proceed until a human says yes or no.

---

## Step 6 - Check the Audit Trail

Click the **Audit** tab. Every decision from the steps above is logged:

- The registration event
- The promotion from QUARANTINE to PROBATION
- The allowed read action
- The gated external call
- Each entry hash-linked to the previous one

The audit chain is tamper-evident - if any entry is modified, the chain fails its integrity check.

---

## Adding a Second Agent

Same process. Repeat Steps 2-5 with a different name. Each agent gets its own `instance_id` and its own independent governance state - separate trust level, separate Manners score, separate action history, separate kill switch. The platform API key is shared; everything else is per-agent.

---

## Agent Types - Which to Use

| Type | Use it when |
|---|---|
| **OpenClaw** | You want the full 8-step governance pipeline. Trust levels, Manners scoring, approval gates, kill switch, anomaly detection - all of it. This is the right choice for any autonomous agent. |
| **Generic** | You have an agent that isn't OpenClaw but you want ClawCoat to track its actions and apply governance. Same pipeline, no OpenClaw-specific assumptions. |
| **DID Agent** | W3C DID-based identity. Selecting this redirects to the Identity tab. Use for agents that authenticate via cryptographic DID rather than API key. |

---

## Reference: Form Fields

| Field | Type | Notes |
|---|---|---|
| Agent Type | Dropdown | OpenClaw / Generic / DID Agent |
| Agent Name | Text | Goes into audit log exactly as typed |
| API Key | Text | Platform API key - hashed before storage |
| Starting Trust Level | Dropdown | Always leave at QUARANTINE for new agents |
| Trust Override Justification | Text | Required and enforced if you choose above QUARANTINE |

---

## Dashboard Tab Quick Reference

| Tab | What it does |
|---|---|
| **Agents** | Register agents, see all agent types in one list |
| **OpenClaw** | Monitor registered instances - trust level, action count, Manners score, promote/demote controls |
| **Approvals** | Review and act on gated actions waiting for human decision |
| **Audit** | Full tamper-evident audit chain - every event, every hash |

---

*ClawCoat v11.0.2 · Quietfire AI · March 19, 2026*
