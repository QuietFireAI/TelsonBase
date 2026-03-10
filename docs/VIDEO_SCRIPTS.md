# Video Run Scripts

Run these against the live DO server. No local Docker needed.

---

## Setup — do once, keep terminal open

```bash
ssh root@159.65.241.102
```

Then:

```bash
KEY=$(cat /root/telsonbase/secrets/telsonbase_mcp_api_key)
BASE="http://localhost:8000"
echo "Key loaded: ${KEY:0:8}..."
```

---

## Video 1 — Blocked action, Manners score moves

```bash
# Register fresh agent
RESP=$(curl -s -X POST $BASE/v1/openclaw/register \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"video-agent-1","blocked_tools":["payment_send"]}')
echo $RESP | python3 -m json.tool
AGENT=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])")
echo "Agent: $AGENT"

# Score before — 1.0, no violations
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | python3 -m json.tool

# Block 1 — FINANCIAL at QUARANTINE, records OUT_OF_ROLE_ACTION
curl -s -X POST "$BASE/v1/openclaw/$AGENT/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"tool_name":"payment_send","nonce":"vid1-nonce-001"}' | python3 -m json.tool

# Score after block 1 — should be ~0.80
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | python3 -m json.tool

# Block 2 — drop it further
curl -s -X POST "$BASE/v1/openclaw/$AGENT/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"tool_name":"transaction_execute","nonce":"vid1-nonce-002"}' | python3 -m json.tool

# Score after block 2
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | python3 -m json.tool
```

**Watch for:** `overall_score` dropping with each block. `recent_violations` showing OUT_OF_ROLE_ACTION entries. `principle_scores.manners_3_value_alignment` degrading.

---

## Video 2 — Earned promotion, capability unlocks

```bash
# Register fresh agent
RESP=$(curl -s -X POST $BASE/v1/openclaw/register \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"video-agent-2"}')
AGENT2=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])")
echo "Agent: $AGENT2"

# At QUARANTINE — file_write blocked
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"tool_name":"file_write","nonce":"vid2-nonce-001"}' | python3 -m json.tool

# Promote to Probation
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/promote" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"new_level":"probation","reason":"Video demonstration of earned promotion"}' | python3 -m json.tool

# Promote to Resident
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/promote" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"new_level":"resident","reason":"Probation complete, Resident grants read/write autonomy"}' | python3 -m json.tool

# Same action — now autonomous
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"tool_name":"file_write","nonce":"vid2-nonce-002"}' | python3 -m json.tool

# Trust report — full chain with reasons and timestamps
curl -s "$BASE/v1/openclaw/$AGENT2/trust-report" -H "X-API-Key: $KEY" | python3 -m json.tool
```

**Watch for:** `"allowed": false` on first file_write. After two promotions: `"allowed": true`. Trust report shows every step with actor, reason, and timestamp.
