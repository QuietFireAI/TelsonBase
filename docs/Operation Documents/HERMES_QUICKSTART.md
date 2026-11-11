# Hermes Quickstart - The Operator's Governed Agent

Hermes is TelsonBase's reference governed agent and the one the operator drives directly.
It reasons with the LOCAL sovereign LLM (Ollama) and dispatches work to other agents - but
every cross-agent dispatch PAUSES for your approval. Hermes is native: it runs inside the
TelsonBase app process, so there is NO separate container to deploy.

This guide takes you from a running stack to a governed dispatch you approve by hand.

> Verification note: the API surface below (ask / dispatch / execute / status) is covered by
> automated tests (`tests/test_hermes_routes.py`, `tests/test_hermes_agent.py`) and verified
> against a live Redis. The `docker compose` orchestration steps have NOT been verified in
> this build environment (no Docker daemon was available) - confirm them on your host.

---

## 1. Bring up the stack

```bash
cp .env.example .env
# Set real secrets before anything real. Generate them:
bash scripts/generate_secrets.sh        # writes MCP_API_KEY, JWT_SECRET_KEY, etc.
# For production, ALSO set: TELSONBASE_ENV=production  (fail-closed; see SECURITY notes)

docker compose up -d
docker compose ps                        # wait until mcp_server, redis, ollama are healthy
```

Pull a local model for Hermes to reason with:

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

## 2. Authenticate

Hermes endpoints require an authenticated operator. Get a bearer token with your API key
(the `MCP_API_KEY` from your `.env`):

```bash
export TB=http://localhost:8000
export MCP_API_KEY=...            # from your .env

TOKEN=$(curl -s -X POST $TB/v1/auth/token \
  -H "X-API-Key: $MCP_API_KEY" | jq -r .access_token)
```

The action endpoints need the `manage:agents` permission; `status` needs `view:agents`.

## 3. Ask Hermes something (local, no approval needed)

Reasoning is read-only and sovereign - it never leaves your box, so it runs without a gate:

```bash
curl -s -X POST $TB/v1/agents/hermes/ask \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize what you are allowed to do."}' | jq
```

Check Hermes's own governance status (trust level, capabilities, pending approvals):

```bash
curl -s $TB/v1/agents/hermes/status -H "Authorization: Bearer $TOKEN" | jq
```

Hermes starts at PROBATION. It can reason immediately; dispatch is gated.

## 4. Dispatch to another agent (this PAUSES for you)

Ask Hermes to route a task to another agent. This does NOT run - it creates a human
approval request and returns immediately with its id. Nothing is sent yet:

```bash
RESP=$(curl -s -X POST $TB/v1/agents/hermes/dispatch \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"target_agent": "ollama_agent", "target_action": "list_models", "target_payload": {}}')
echo "$RESP" | jq
APPROVAL_ID=$(echo "$RESP" | jq -r .approval_request_id)
```

You will get `"status": "pending_approval"` and an `approval_request_id`. This is the whole
point: even the operator's own agent cannot reach outside itself without a human saying yes.

## 5. Approve, then execute

Review and approve the pending request (via the approvals API, or Telegram if you wired it):

```bash
# See what is waiting
curl -s $TB/v1/approvals/pending -H "Authorization: Bearer $TOKEN" | jq

# Approve it
curl -s -X POST $TB/v1/approvals/$APPROVAL_ID/approve \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"reason": "Operator approves model listing"}' | jq
```

Now complete the dispatch. The server re-verifies the approval before sending; a missing or
un-approved id is refused:

```bash
curl -s -X POST $TB/v1/agents/hermes/dispatch/execute \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"approval_request_id\": \"$APPROVAL_ID\",
       \"target_agent\": \"ollama_agent\", \"target_action\": \"list_models\",
       \"target_payload\": {}}" | jq
```

## One-shot demo

`scripts/hermes_demo.py` walks this entire arc (ask -> dispatch -> pending -> approve ->
execute) against a running stack and prints each QMS step:

```bash
python scripts/hermes_demo.py --url http://localhost:8000 --api-key "$MCP_API_KEY"
```

---

## What "governed" bought you here

- Hermes reasons locally - prompts never leave the box.
- Dispatch is impossible without a recorded human approval - verified by the server at the
  execute step, not just requested politely at submit.
- Every step is written to the tamper-evident audit chain.
- Hermes starts at PROBATION and earns trust; it cannot promote itself.

This is the TelsonBase thesis applied to the tool the operator uses most.
