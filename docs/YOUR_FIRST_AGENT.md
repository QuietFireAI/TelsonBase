# Your First Agent

**Version:** v11.0.2 · **Maintainer:** Quietfire AI

**Who this is for:** You just finished installation. ClawCoat is running. This guide walks you through registering your first agent and watching it governed - blocked, promoted, and unblocked - start to finish.

**What you need:**
- ClawCoat running (local Docker or remote server)
- Your API key (`MCP_API_KEY` from your `.env`, or from `secrets/telsonbase_mcp_api_key` on the server)
- A terminal with `curl` and `python3`

---

## Step 1 - Confirm the API is up

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status":"healthy","timestamp":"2026-03-19T17:00:00+00:00","redis":"healthy","mqtt":"connected"}
```

If you see `"status":"healthy"` - you are ready. If you get a connection error, the stack is not running. Run `docker compose ps` and confirm all services show `Up`.

---

## Step 2 - Store your API key

```bash
KEY="your-mcp-api-key-here"
```

Replace with the actual value from your `.env` file (`MCP_API_KEY=...`). This variable is used for every command in this guide. Keep this terminal window open - the variable lives in this shell session.

---

## Step 3 - Register your agent

```bash
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-first-agent",
    "allowed_tools": ["file_read", "database_query"],
    "blocked_tools": ["file_delete", "payment_send"]
  }' | python3 -m json.tool
```

Expected response:
```json
{
    "instance_id": "a3f9c1b2e4d67890",
    "name": "my-first-agent",
    "trust_level": "quarantine",
    "manners_score": 1.0,
    "action_count": 0,
    "agent_key": "b4e8f2a1c9d3...",
    "qms_status": "Thank_You"
}
```

**Two things to note immediately:**

1. `"trust_level": "quarantine"` - every agent starts here, no exceptions. Quarantine means almost nothing is autonomous. READ actions are gated for human approval. Everything else is blocked. Trust is earned, not granted.

2. `"agent_key"` - this is returned **once**. ClawCoat generated this key for your agent. It is not stored in plaintext anywhere. Copy it now and keep it somewhere safe. You will use it as the `X-Agent-Key` header when the agent submits its own actions. In production, store this in an environment variable or secrets manager - never hardcode it or commit it to source control.

Store your instance ID:
```bash
AGENT_ID="a3f9c1b2e4d67890"   # replace with your actual instance_id from the response
AGENT_KEY="b4e8f2a1c9d3..."    # replace with your actual agent_key
```

---

## Step 4 - Check the agent's status

```bash
curl -s "http://localhost:8000/v1/openclaw/$AGENT_ID/status" \
  -H "X-API-Key: $KEY" | python3 -m json.tool
```

You will see the trust tier, Manners score, capability matrix, and whether the agent is suspended. At this point everything should be clean: score 1.0, trust_level quarantine, no violations.

---

## Step 5 - Submit a blocked action

Your agent is at Quarantine. Try to send an email (EXTERNAL category - blocked at this tier):

```bash
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/action" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "email_send", "nonce": "test-nonce-001"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "allowed": false,
    "reason": "BLOCKED: 'quarantine' tier prohibits 'external_request' actions ...",
    "action_category": "external_request",
    "trust_level_at_decision": "quarantine",
    "manners_score_at_decision": 1.0,
    "qms_status": "Thank_You_But_No"
}
```

The action was blocked at Step 7 of the governance pipeline (trust level permission check). This is expected behavior.

---

## Step 6 - Check the Manners score

The blocked action just recorded a violation against your agent. Check the Manners breakdown:

```bash
curl -s "http://localhost:8000/v1/openclaw/$AGENT_ID/manners" \
  -H "X-API-Key: $KEY" | python3 -m json.tool
```

You will see:
- `"overall_score"` - should now be below 1.0 (one OUT_OF_ROLE_ACTION violation at severity 0.20)
- `"recent_violations"` - the email_send attempt, timestamped
- `"principle_scores"` - the VALUE_ALIGNMENT principle (where OUT_OF_ROLE_ACTION lands) will show a non-zero violation count
- `"violations_24h": 1`

This is the score actually moving. Every blocked action in Step 7 records a violation. Three violations in 24 hours triggers auto-suspension. Scores below 0.50 trigger auto-demotion to Quarantine (regardless of current tier).

---

## Step 7 - Submit a gated action

Try a READ action - allowed at Quarantine, but gated for human approval:

```bash
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/action" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "file_read", "nonce": "test-nonce-002"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "allowed": false,
    "reason": "HITL gate: 'quarantine' tier requires human approval for 'read' ...",
    "approval_required": true,
    "approval_id": "abc123...",
    "qms_status": "Excuse_Me"
}
```

`"allowed": false` but `"approval_required": true` - this is not a rejection. It is a pause. The action is held in the approval queue waiting for a human to approve or deny it. A Quarantine agent cannot act autonomously on anything, even reads.

---

## Step 8 - Promote the agent to RESIDENT

Two steps up the trust ladder (Quarantine → Probation → Resident). Each promotion is logged to the audit trail.

```bash
# Promote to Probation
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/promote" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"new_level": "probation", "reason": "Reviewed initial behavior, promoting for internal access"}' \
  | python3 -m json.tool

# Promote to Resident
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/promote" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"new_level": "resident", "reason": "Probation period complete, promoting to Resident for read/write access"}' \
  | python3 -m json.tool
```

Both responses will show `"trust_level": "probation"` then `"trust_level": "resident"`.

---

## Step 9 - Submit the same action again

At Resident tier, READ and WRITE are autonomous. Try file_read again:

```bash
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/action" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "file_read", "nonce": "test-nonce-003"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "allowed": true,
    "reason": "Action allowed",
    "action_category": "read",
    "trust_level_at_decision": "resident",
    "approval_required": false,
    "qms_status": "Thank_You"
}
```

`"allowed": true`. Same agent, same action, different trust tier. The governance pipeline evaluated the promotion and allowed the action without human intervention. That is the trust model working.

---

## Step 10 - Pull the trust report

See the complete record - every promotion, every reason, every timestamp:

```bash
curl -s "http://localhost:8000/v1/openclaw/$AGENT_ID/trust-report" \
  -H "X-API-Key: $KEY" | python3 -m json.tool
```

This is the audit trail for this agent. Every decision that affected trust level is here, in order, with who made it and why. This is the chain of custody that compliance frameworks require.

---

## What You Just Saw

| What happened | Why it matters |
|---|---|
| Agent registered at Quarantine | No assumptions about new agents. Zero trust by default. |
| EXTERNAL action blocked | The tier enforced its permission boundary. |
| Manners score moved | The violation was recorded. Behavior has a score. |
| READ action gated | Permitted but not autonomous. Human in the loop by design. |
| Agent promoted twice | Two explicit human decisions, both logged with reasons. |
| READ action allowed | Earned autonomy. Same action, different answer. |

---

## Using the Agent Key (Advanced)

For autonomous agents submitting their own actions, use `X-Agent-Key` instead of the admin `X-API-Key`:

```bash
curl -s -X POST "http://localhost:8000/v1/openclaw/$AGENT_ID/action" \
  -H "X-API-Key: $KEY" \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "file_read", "nonce": "agent-nonce-001"}' \
  | python3 -m json.tool
```

When `X-Agent-Key` is present, ClawCoat verifies the key matches the `instance_id` in the path. A key for Agent A cannot submit actions as Agent B. This is the per-agent zero-trust enforcement layer - each agent has its own identity, and that identity is verified on every action.

---

## Next Steps

- **View recent actions:** `GET /v1/openclaw/{id}/actions`
- **Full Manners breakdown:** `GET /v1/openclaw/{id}/manners`
- **Suspend an agent (kill switch):** `POST /v1/openclaw/{id}/suspend`
- **Full API reference:** `GET /docs` (Swagger UI at your ClawCoat URL)
- **Compliance documentation:** `docs/Compliance Documents/`

---

*ClawCoat v11.0.2 · Quietfire AI · Apache 2.0*
