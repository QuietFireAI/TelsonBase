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

The server-side script `/root/telsonbase/video1.sh` runs this automatically.
From an SSH session on the DO server:

```bash
bash /root/telsonbase/video1.sh
```

Or run manually (uses timestamped agent name and nonces to avoid replay errors on repeat runs):

```bash
TS=$(date +%s)
AGNAME="vid1-$TS"

# Register fresh agent
RESP=$(curl -s -X POST $BASE/v1/openclaw/register \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"name\":\"$AGNAME\",\"blocked_tools\":[\"payment_send\"]}")
echo $RESP | python3 -m json.tool
AGENT=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])")

# Score before — 1.0, no violations
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('score:', d['overall_score'], 'violations_24h:', d['violations_24h'])"

# Block 1 — payment_send on blocklist (CAPABILITY_VIOLATION)
curl -s -X POST "$BASE/v1/openclaw/$AGENT/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"tool_name\":\"payment_send\",\"nonce\":\"n${TS}-1\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('allowed:', d['allowed'], 'reason:', d['reason'])"

# Score after block 1
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('score:', d['overall_score'], 'violations_24h:', d['violations_24h'])"

# Block 2 — transaction_execute (financial at QUARANTINE, OUT_OF_ROLE_ACTION)
curl -s -X POST "$BASE/v1/openclaw/$AGENT/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"tool_name\":\"transaction_execute\",\"nonce\":\"n${TS}-2\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('allowed:', d['allowed'], 'reason:', d['reason'])"

# Score after block 2
curl -s "$BASE/v1/openclaw/$AGENT/manners" -H "X-API-Key: $KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('score:', d['overall_score'], 'violations_24h:', d['violations_24h'])"
```

**Watch for:** `overall_score` dropping after each block (1.0 → 0.95 → 0.91). Two different violation types: CAPABILITY_VIOLATION (blocklist) and OUT_OF_ROLE_ACTION (tier restriction). `violations_24h` incrementing.

---

## Video 2 — Earned promotion, capability unlocks

The server-side script `/root/telsonbase/video2.sh` runs this automatically.
From an SSH session on the DO server:

```bash
bash /root/telsonbase/video2.sh
```

Or run manually (uses timestamped agent name and nonces):

```bash
TS=$(date +%s)
AGNAME="vid2-$TS"

# Register fresh agent
RESP=$(curl -s -X POST $BASE/v1/openclaw/register \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"name\":\"$AGNAME\"}")
AGENT2=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])")
echo "Agent: $AGENT2"

# At QUARANTINE — file_write blocked
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"tool_name\":\"file_write\",\"nonce\":\"n${TS}-1\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('allowed:', d['allowed'], 'reason:', d['reason'])"

# Promote to Probation
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/promote" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"new_level":"probation","reason":"Video demonstration of earned promotion"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('trust_level:', d['new_trust_level'])"

# Promote to Resident
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/promote" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"new_level":"resident","reason":"Probation complete, Resident grants read/write autonomy"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('trust_level:', d['new_trust_level'])"

# Same action — now autonomous
curl -s -X POST "$BASE/v1/openclaw/$AGENT2/action" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d "{\"tool_name\":\"file_write\",\"nonce\":\"n${TS}-2\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('allowed:', d['allowed'])"

# Trust report — full chain with reasons and timestamps
curl -s "$BASE/v1/openclaw/$AGENT2/trust-report" -H "X-API-Key: $KEY" | python3 -m json.tool
```

**Watch for:** `"allowed": False` on first file_write. After two promotions: `"allowed": True`. Trust report shows every step with actor, reason, and timestamp.
