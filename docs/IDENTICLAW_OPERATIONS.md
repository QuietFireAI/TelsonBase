# Identiclaw Agent Operations Guide

## TelsonBase v7.3.0CC — DID-Based Agent Identity

**Architecture**: Hybrid — Identiclaw issues the driver's license (DID + credentials on Cloudflare). TelsonBase is the racetrack (all operations governed locally).

---

## Quick Start

### 1. Enable the Integration

In `.env`, flip the master switch:

```
IDENTICLAW_ENABLED=true
```

Rebuild and restart:

```bash
docker compose build mcp_server && docker compose up -d mcp_server worker beat
```

Verify in logs:

```bash
docker compose logs mcp_server | grep "Identiclaw"
# Should see: "REM: Identiclaw MCP-I identity engine enabled_Thank_You"
```

### 2. Create Your Identiclaw Agent

Go to [kya.vouched.id/identiclaw](https://kya.vouched.id/identiclaw) and follow their 3-step wizard:

1. **Create Cloudflare API token** (Workers Scripts, KV, R2, Durable Objects permissions)
2. **Deploy agent** via wizard — choose Anthropic or OpenAI, give it a name
3. **Deploy to Cloudflare** — `npx wrangler deploy` or GitHub integration

You'll get:
- A **DID** (e.g., `did:key:z6MkhaXgBZDvotDkL5fhnutmA...`) — the agent's identity
- An **Ed25519 keypair** — for signing requests
- **Verifiable Credentials** — scoped permissions from Identiclaw

### 3. Register the Agent on TelsonBase

```bash
API_KEY="your-telsonbase-api-key"

curl -X POST http://localhost:8000/v1/identity/register \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "did": "did:key:z6MkhaXgBZDvotDkL5fhnutmA...",
    "display_name": "MyFirstClaw",
    "credentials": [
      {
        "id": "vc-001",
        "type": ["VerifiableCredential", "AgentCapability"],
        "issuer": "did:web:identiclaw.com",
        "issuanceDate": "2026-02-17T00:00:00Z",
        "expirationDate": "2026-03-17T00:00:00Z",
        "credentialSubject": {
          "id": "did:key:z6MkhaXgBZDvotDkL5fhnutmA...",
          "scopes": ["agent:read", "agent:write", "mcp:tool:invoke"]
        },
        "proof": {
          "type": "Ed25519Signature2020",
          "proofValue": ""
        }
      }
    ],
    "manners_md_path": "/agents/manners/my_first_claw_manners.md",
    "profession_md_path": "/agents/professions/my_first_claw.md"
  }'
```

Response:

```json
{
  "did": "did:key:z6MkhaXgBZDvotDkL5fhnutmA...",
  "display_name": "MyFirstClaw",
  "trust_level": "quarantine",
  "telsonbase_permissions": ["read", "tool_invoke", "write"],
  "revoked": false,
  "registered_at": "2026-02-17T12:30:00+00:00",
  "qms_status": "Thank_You"
}
```

The agent starts at **QUARANTINE** trust level. It can authenticate, but its actions are limited until you promote it.

### 4. Agent Authenticates via X-DID-Auth Header

When the Identiclaw agent makes requests to TelsonBase, it sends:

```
X-DID-Auth: did:key:z6Mk...|<base64-signature>|<nonce>|<unix-timestamp>
```

The signature is computed over `nonce + timestamp + request_path + request_method` using the agent's Ed25519 private key. TelsonBase verifies locally (no network call).

---

## Dashboard Integration

### Admin Dashboard (http://localhost:8000/dashboard)

The **Identity** tab shows all registered DID agents:

- **Agent cards** with DID, display name, trust level badge, and revocation status
- **Permission list** mapped from Verifiable Credential scopes
- **MANNERS.md / Profession.md** links for behavioral constraint files
- **Action buttons**: Revoke (kill switch), Reinstate, Refresh Credentials
- **Registration form** for onboarding new DID agents

### What You See

| Column | Description |
|---|---|
| Display Name | Human-readable agent name |
| DID | Truncated identifier (expandable) |
| Trust Level | quarantine / probation / resident / citizen |
| Permissions | Mapped from VC scopes (e.g., read, write, tool_invoke) |
| Status | Active (green) or Revoked (red) |
| Registered | When the agent was first registered |
| Last Verified | When the agent last successfully authenticated |
| MANNERS.md | Link to the agent's ethics constraint file |
| Profession.md | Link to the agent's job description |

### Approval Queue

When a new DID agent registers, it triggers the `rule-did-first-registration` approval rule. You'll see it in the **Approvals** tab:

- Priority: **HIGH**
- Action: `identity.register`
- Description: Agent DID, display name, requested scopes
- You must **Approve** before the agent can authenticate

Similarly, if an agent presents credentials with expanded scopes, `rule-did-scope-change` fires.

### Audit Trail

All identity events appear in the **Audit Trail** tab:

| Event Type | When It Fires |
|---|---|
| `identity.registered` | New DID agent registered |
| `identity.verified` | DID signature verified on auth |
| `identity.verification_failed` | Auth attempt failed (bad sig, expired, etc.) |
| `identity.revoked` | Kill switch activated |
| `identity.reinstated` | Agent reinstated after review |
| `identity.credential_updated` | Credentials refreshed |

---

## Day-to-Day Operations

### List All DID Agents

```bash
curl -s http://localhost:8000/v1/identity/list \
  -H "X-API-Key: $API_KEY" | jq
```

### Get Agent Details

```bash
curl -s "http://localhost:8000/v1/identity/did:key:z6Mk..." \
  -H "X-API-Key: $API_KEY" | jq
```

### Kill Switch (Immediate Revocation)

```bash
curl -X POST "http://localhost:8000/v1/identity/revoke/did:key:z6Mk..." \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Compromised key detected"}'
```

This is **instant and local**. The agent cannot authenticate on the next request, regardless of Identiclaw's status. The revocation survives container restarts (Redis-persisted).

### Reinstate After Review

```bash
curl -X POST "http://localhost:8000/v1/identity/reinstate/did:key:z6Mk..." \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Key rotated, reviewed and cleared"}'
```

### Force Refresh Credentials

```bash
curl -X POST http://localhost:8000/v1/identity/refresh-credentials \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"did": "did:key:z6Mk..."}'
```

Re-resolves the DID document and updates the cached public key. Use after key rotation.

---

## Trust Level Progression

DID agents follow the same trust system as all TelsonBase agents:

```
QUARANTINE → PROBATION → RESIDENT → CITIZEN
```

| Level | What the Agent Can Do |
|---|---|
| **Quarantine** | Authenticate only. All actions require approval gates. |
| **Probation** | Low-risk actions auto-approved. High-risk still gated. |
| **Resident** | Most actions auto-approved. External comms still gated. |
| **Citizen** | Full permissions within VC scope. Kill switch still works. |

Promote via the Agents tab in the dashboard or programmatically.

---

## Permission Mapping (VC Scopes → TelsonBase Permissions)

| Identiclaw Scope | TelsonBase Permission(s) |
|---|---|
| `agent:read` | `read` |
| `agent:write` | `read`, `write` |
| `agent:execute` | `read`, `write`, `execute` |
| `agent:admin` | `*` (wildcard) |
| `mcp:tool:invoke` | `tool_invoke` |
| `mcp:tool:list` | `tool_list` |
| `mcp:resource:read` | `read` |
| `mcp:resource:write` | `write` |
| `telsonbase:llm:chat` | `llm_chat` |
| `telsonbase:workflow:execute` | `workflow_execute` |
| `telsonbase:system:analyze` | `system_analyze` |

**Unknown scopes grant zero permissions** (fail-closed). Add custom mappings in `core/identiclaw.py` → `SCOPE_PERMISSION_MAP`.

---

## MANNERS.md and Profession.md

Each DID agent can have two constraint files:

- **MANNERS.md** — Ethics and boundaries. What the agent **won't** do. Based on Anthropic's safety principles.
- **Profession.md** — Job description. What the agent **should** do. Skills, responsibilities, expected behaviors.

Set these paths during registration:

```json
{
  "manners_md_path": "/agents/manners/my_claw_manners.md",
  "profession_md_path": "/agents/professions/my_claw_profession.md"
}
```

These are stored in the identity record and visible in the dashboard. The Manners framework runtime (`core/manners.py`) can reference them for compliance checks.

---

## Security Architecture

### What Stays Local (on TelsonBase)
- Ed25519 signature verification (cryptography library, no external call)
- Kill switch (in-memory + Redis, immediate, overrides Identiclaw)
- Permission mapping (VC scopes → TelsonBase permissions)
- All agent operations (approval gates, egress gateway, audit trail)
- Nonce replay protection (Redis, 5-minute window)

### What Touches Cloudflare (via Egress Gateway)
- Initial DID document resolution (cache miss, every 24h per DID)
- Agent registration on Identiclaw (their wizard, one-time)
- Know That AI reputation lookup (optional, periodic)

### Egress Domains Whitelisted
- `identity.identiclaw.com` — DID resolution
- `workers.identiclaw.com` — Agent registration
- `knowthat.ai` — Reputation registry

---

## Troubleshooting

### "Identiclaw integration is disabled"
Set `IDENTICLAW_ENABLED=true` in `.env` and restart.

### "DID not in cache and cannot resolve locally"
The agent's DID hasn't been registered yet. Register it first via `/v1/identity/register`.

### "DID authentication failed"
Check: Is the agent revoked? Is the timestamp within 5 minutes? Is the nonce fresh? Is the signature valid?

### "VC issuer not trusted"
The credential's issuer DID isn't in `IDENTICLAW_KNOWN_ISSUERS`. Add it to `.env`:
```
IDENTICLAW_KNOWN_ISSUERS=["did:web:identiclaw.com","did:web:your-issuer.com"]
```

### Agent stuck at quarantine
Promote via dashboard or API. Quarantine is intentional — new agents must earn trust.
