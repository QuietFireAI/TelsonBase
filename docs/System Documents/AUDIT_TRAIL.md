# TelsonBase Audit Trail
**Version:** v11.0.1 · **Maintainer:** Quietfire AI

Every governance decision made by TelsonBase is written to a hash-chained audit record. Not logged to a file. Not stored in a table. **Hash-chained** - each entry cryptographically binds to the one before it. You can hand this record to a regulator, opposing counsel, or a forensic investigator and prove that nothing was altered after the fact.

This document covers the implementation, the API, the real-time stream, and the limits you need to know about before you go to production.

---

## Why Hash Chaining Matters for AI Agent Governance

Conventional log files can be edited. A compromised system can append to them, truncate them, or rewrite them. This is an obvious problem when the thing being logged is an AI agent with file system access.

TelsonBase's audit chain uses the same principle as a blockchain - without the overhead. Every entry contains a SHA-256 hash computed over its own content plus the hash of the previous entry. To silently alter entry #4,200, you would need to recompute the hash of #4,200, then #4,201, then every entry after it, and update the chain state stored in Redis - all without triggering a verification failure. In practice: if the chain shows `valid`, nothing was tampered with. If it shows `invalid`, something was.

The genesis entry uses a 64-character zero hash (`0000...0000`) as its `previous_hash`. From there, every entry is linked.

---

## What the Chain Captures

The chain records every event that matters to governance and compliance. Not infrastructure noise - not health checks, not Redis PING/PONG - governance events.

### Authentication
| Event Type | Triggered by |
|---|---|
| `auth.success` | Successful API key or JWT authentication |
| `auth.failure` | Failed authentication attempt |
| `auth.token_issued` | JWT issued to a user |

### Agent Governance (OpenClaw)
| Event Type | Triggered by |
|---|---|
| `openclaw.registered` | New agent instance registered |
| `openclaw.action_allowed` | Action passed the 8-step governance pipeline |
| `openclaw.action_blocked` | Action rejected (blocklist, kill switch, policy) |
| `openclaw.action_gated` | Action sent to human approval queue |
| `openclaw.trust_promoted` | Trust level raised (Quarantine → Probation, etc.) |
| `openclaw.trust_demoted` | Trust level lowered - includes Manners auto-demotion |
| `openclaw.suspended` | Kill switch activated |
| `openclaw.reinstated` | Kill switch cleared by a human |

### Approvals & Anomalies
| Event Type | Triggered by |
|---|---|
| `approval.granted` | Human approved a gated action |
| `anomaly.detected` | Behavioral anomaly flagged (rate spike, capability probe, enumeration) |
| `capability.check` | Agent capability enforcement check |

### Agent Identity (Identiclaw)
| Event Type | Triggered by |
|---|---|
| `identity.registered` | New DID agent registered |
| `identity.verified` | Ed25519 signature verified |
| `identity.verification_failed` | Signature check failed |
| `identity.revoked` | Agent DID revoked |
| `identity.reinstated` | Agent DID reinstated after review |
| `identity.credential_updated` | Verifiable credential refreshed |

### Toolroom
| Event Type | Triggered by |
|---|---|
| `tool.registered` | New tool added |
| `tool.checkout` | Agent checked out a tool |
| `tool.return` | Agent returned a tool |
| `tool.quarantined` | Tool flagged for security review |
| `tool.hitl_gate` | HITL approval required for tool operation |

### System & Tasks
| Event Type | Triggered by |
|---|---|
| `system.startup` / `system.shutdown` | Container lifecycle |
| `task.dispatched` / `task.completed` / `task.failed` | Agent task execution |
| `external.request` / `external.blocked` | Egress firewall decisions |
| `security.alert` | Security anomaly detected |
| `security.qms_bypass` | Message received without QMS formatting |

---

## Actor Types

Every entry records not just *who* acted, but *what kind of actor* they are. This satisfies HIPAA 45 CFR 164.312(a)(2)(i) unique user identification requirements.

| Actor Type | Meaning |
|---|---|
| `human` | Authenticated human operator |
| `ai_agent` | Autonomous AI agent |
| `system` | Internal platform process |
| `service_account` | Automated service credential |
| `emergency` | Break-the-glass access |

---

## Entry Structure

Every chain entry has the same shape:

```json
{
  "sequence": 4207,
  "timestamp": "2026-02-23T18:44:12.003Z",
  "event_type": "openclaw.trust_demoted",
  "message": "Agent web_agent demoted: RESIDENT → PROBATION - Manners score 0.41 < 0.50 threshold_Thank_You_But_No",
  "actor": "system:governance",
  "actor_type": "system",
  "resource": "web_agent",
  "details": {
    "agent_id": "web_agent",
    "from_level": "RESIDENT",
    "to_level": "PROBATION",
    "reason": "manners_auto_demotion",
    "manners_score": 0.41
  },
  "previous_hash": "a3f8c2e1d09b...",
  "entry_hash": "7d4f91e2b80a..."
}
```

The `entry_hash` is SHA-256 of the canonical JSON of `sequence + timestamp + event_type + message + actor + actor_type + resource + details + previous_hash` with sorted keys and no whitespace. You can recompute it yourself to verify any entry independently of the API.

---

## Storage Architecture

| Layer | Capacity | Persistence |
|---|---|---|
| In-memory | 1,000 most recent entries | Cleared on restart |
| Redis sorted set (`audit:chain:entries`) | 100,000 entries (configurable) | Survives restarts |
| Redis chain state | Current sequence, last hash, chain ID | Survives restarts |

**The 100K Redis cap** is controlled by `AUDIT_MAX_REDIS_ENTRIES` in your `.env`. When the cap is reached, oldest entries are trimmed. The chain state (last sequence, last hash) is preserved - new entries continue chaining from where they left off. The trimmed entries are gone unless you've exported them.

**Verification scope**: `GET /v1/audit/chain/verify` verifies the last N entries loaded into memory (default: 100, max: 1,000). A verification pass against 100 entries tells you those 100 are intact. To verify the full chain, export it and verify offline, or increase the verification limit.

**On restart**: chain entries are reloaded from Redis. If the last loaded entry's hash doesn't match the saved chain state, TelsonBase discards the stale in-memory entries rather than introduce a false chain break at the session boundary. This is logged as a warning.

---

## API Reference

All audit endpoints require the `view:audit` permission. Authentication via `X-API-Key` header or `Authorization: Bearer` token.

### Get Chain Status
```
GET /v1/audit/chain/status
```
Returns the current chain ID, last sequence number, last hash, entry count, and in-memory entry count.

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/audit/chain/status
```

```json
{
  "chain_id": "a1b2c3d4e5f6",
  "last_sequence": 54327,
  "last_hash": "7d4f91e2b80a...",
  "created_at": "2026-02-20T09:00:00Z",
  "entries_count": 54327,
  "in_memory_entries": 1000
}
```

### Get Recent Entries
```
GET /v1/audit/chain/entries?limit=50
```
Returns the most recent N entries (default: 50, max: 500), oldest first.

```bash
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/v1/audit/chain/entries?limit=100"
```

### Verify Chain Integrity
```
GET /v1/audit/chain/verify?limit=100
```
Verifies both hash integrity (each entry's `entry_hash` matches its computed hash) and chain linkage (each entry's `previous_hash` matches the prior entry's `entry_hash`). Returns the specific sequence numbers where breaks are found, if any.

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/audit/chain/verify
```

```json
{
  "valid": true,
  "entries_checked": 100,
  "breaks": [],
  "chain_id": "a1b2c3d4e5f6",
  "first_sequence": 54228,
  "last_sequence": 54327,
  "message": "Chain verified successfully"
}
```

A failed verification response includes the break details:

```json
{
  "valid": false,
  "entries_checked": 100,
  "breaks": [
    {
      "sequence": 54291,
      "issue": "hash_mismatch",
      "expected": "7d4f91...",
      "computed": "3a8bc2..."
    }
  ]
}
```

### Export Chain
```
GET /v1/audit/chain/export?start_sequence=0
```
Returns chain entries with verification status for compliance export. Accepts optional `start_sequence` and `end_sequence` to export a range.

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/v1/audit/chain/export?start_sequence=50000" \
  -o audit_export.json
```

---

## Real-Time Stream (SSE)

```
GET /v1/audit/stream?api_key=YOUR_KEY&last_sequence=0
```

New entries are pushed as [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) within approximately 2 seconds of being written to the chain. Use `last_sequence` to receive only entries you haven't seen yet - pass the sequence number of the last entry you received to resume without re-receiving old entries.

**Authentication note**: Browser `EventSource` cannot send custom headers. The `api_key` query parameter is the authentication mechanism for this endpoint specifically. On a local self-hosted deployment this is acceptable. If you're exposing TelsonBase to a network boundary, put it behind Traefik with TLS and rate-limit the endpoint.

### Browser / JavaScript

```javascript
const key = localStorage.getItem('telsonbase_api_key');
const lastSeq = 54327; // last sequence you've seen

const es = new EventSource(
  `/v1/audit/stream?api_key=${encodeURIComponent(key)}&last_sequence=${lastSeq}`
);

es.onopen = () => console.log('Audit stream connected');

es.onmessage = (event) => {
  const entry = JSON.parse(event.data);
  console.log(`[${entry.sequence}] ${entry.event_type} - ${entry.actor}: ${entry.message}`);
};

es.onerror = () => {
  console.warn('Audit stream disconnected');
  es.close();
};

// Clean up when done
// es.close();
```

### Python

```python
import httpx
import json

url = "http://localhost:8000/v1/audit/stream"
params = {"api_key": API_KEY, "last_sequence": 0}

with httpx.stream("GET", url, params=params, timeout=None) as response:
    for line in response.iter_lines():
        if line.startswith("data:"):
            entry = json.loads(line[5:].strip())
            print(f"[{entry['sequence']}] {entry['event_type']} - {entry['actor']}")
```

### Shell (curl)

```bash
curl -N "http://localhost:8000/v1/audit/stream?api_key=$API_KEY&last_sequence=0"
```

The stream sends `: keepalive` comment lines when no new entries arrive. These maintain the connection through proxies and load balancers that close idle connections.

---

## Dashboard Integration

The TelsonBase admin dashboard (`/dashboard` → Audit Trail tab) connects to the SSE stream when you're on the tab and authenticated. You'll see a pulsing green indicator labeled **"Live stream · entries pushed in real-time"** when the EventSource connection is open. If the SSE endpoint is unreachable, it falls back to a 10-second poll and shows **"Polling · refreshing every 10s"** in amber.

The **Verify Chain** button in the dashboard calls `POST /v1/audit/chain/verify` and displays the result inline - no browser `alert()`, no page reload. The **Export JSON** button fetches up to 1,000 entries via the API client (with authentication headers) and downloads `audit_export.json` to your machine.

---

## Verify an Entry Offline

You don't need the TelsonBase API to verify a single entry. The hash is deterministic and reproducible:

```python
import json
import hashlib

entry = {
    "sequence": 4207,
    "timestamp": "2026-02-23T18:44:12.003Z",
    "event_type": "openclaw.trust_demoted",
    "message": "Agent web_agent demoted_Thank_You_But_No",
    "actor": "system:governance",
    "actor_type": "system",
    "resource": "web_agent",
    "details": {"from_level": "RESIDENT", "to_level": "PROBATION"},
    "previous_hash": "a3f8c2e1d09b..."
}

content = json.dumps(entry, sort_keys=True, separators=(',', ':'))
computed = hashlib.sha256(content.encode('utf-8')).hexdigest()

print(computed == entry_hash_from_api)  # True if unmodified
```

The fields hashed are: `sequence`, `timestamp`, `event_type`, `message`, `actor`, `actor_type`, `resource`, `details`, `previous_hash`. The `entry_hash` field itself is not included in the hash input (it's the output).

---

## Extending the Chain

To log a custom event from your own code:

```python
from core.audit import audit, AuditEventType

audit.log(
    event_type=AuditEventType.AGENT_ACTION,
    message="Custom governance action taken",
    actor="my_service",
    actor_type="service_account",
    resource="target_resource_id",
    details={"key": "value"},
    qms_status="Thank_You"
)
```

The `qms_status` parameter appends a QMS suffix to the message (`_Thank_You`, `_Thank_You_But_No`, `_Please`, etc.) for consistency with the rest of the platform's internal messaging protocol.

---

## Known Limitations

**100K Redis cap**: The default `AUDIT_MAX_REDIS_ENTRIES=100000` is hit in approximately 12 hours under active governance load. Once hit, oldest entries are trimmed. If you need long-term retention, export the chain on a schedule and archive externally. PostgreSQL archival is on the active development roadmap.

**Verification window**: Chain verification operates on the in-memory window (last 1,000 entries) plus whatever Redis returns. You cannot verify the full chain via the API once entries are trimmed. Export first, then verify the export.

**In-memory/state mismatch after restart**: If Redis entries from a previous session don't match the saved chain state, TelsonBase discards the in-memory entries. The chain tip is preserved and new entries continue from there. This appears as a gap in sequence numbers but does not corrupt the ongoing chain.

---

## Proof Sheet

`proof_sheets/TB-PROOF-009_audit_chain_sha256.md` - SHA-256 hash-chained audit trail verification. `proof_sheets/TB-PROOF-046_security_audit_trail.md` - audit trail integrity tests from the security battery: chain creation, hash verification, tamper detection, and UTC timestamp enforcement. Run:

```bash
docker compose exec mcp_server python -m pytest tests/test_audit.py -v
```

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
