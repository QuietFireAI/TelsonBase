# TelsonBase Disaster Recovery Plan

**Version:** 7.3.0CC
**Last Updated:** February 23, 2026
**Architect:** Jeff Phillips — support@telsonbase.com
**AI Model Collaborators:** ChatGPT 3.5/4.0, Gemini 3, Claude Sonnet 4.5, Claude Opus 4.5

---

## 1. Overview

This document outlines disaster recovery procedures for TelsonBase deployments. It covers backup strategies, recovery procedures, and business continuity measures.

### Recovery Objectives

| Metric | Target | Notes |
|--------|--------|-------|
| **RTO** (Recovery Time Objective) | < 4 hours | Full system restoration |
| **RPO** (Recovery Point Objective) | < 1 hour | Data loss tolerance |
| **MTTR** (Mean Time To Recovery) | < 2 hours | For common scenarios |

---

## 2. Architecture Components

### Critical Data Stores

| Component | Data | Persistence | Backup Strategy |
|-----------|------|-------------|-----------------|
| **Redis** | Agent keys, capabilities, anomalies, approvals, federation state | RDB + AOF | Automated snapshots |
| **Audit Logs** | Cryptographically chained events | File system | Log rotation + archive |
| **Encryption Keys** | Master encryption key, salt | Environment variables | Secure vault storage |
| **TLS Certificates** | mTLS certs for federation | File system | Certificate store backup |

### Service Dependencies

```
                    ┌─────────────────┐
                    │   Traefik       │  (Stateless - rebuild from config)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI       │  (Stateless - container image)
                    │   main.py       │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│    Redis      │   │   Mosquitto   │   │    Ollama     │
│  (Critical)   │   │ (Recoverable) │   │ (Recoverable) │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## 3. Backup Procedures

### 3.1 Automated Backups

The backup_agent performs scheduled backups:

```python
# Configure in docker-compose.yml or env
BACKUP_SCHEDULE=daily  # daily, hourly
BACKUP_RETENTION_DAYS=30
```

**What's Backed Up:**
- Redis RDB snapshot
- Agent signing keys (encrypted)
- Capability definitions
- Federation relationships
- Anomaly baselines
- Approval states
- Audit chain state

### 3.2 Manual Backup

```bash
# Trigger immediate backup via API
curl -X POST -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/tasks/dispatch \
  -H "Content-Type: application/json" \
  -d '{"task_name": "backup", "kwargs": {"backup_type": "full"}}'

# Or direct Redis backup
docker exec telsonbase_redis redis-cli BGSAVE
docker cp telsonbase_redis:/data/dump.rdb ./backups/
```

### 3.3 Audit Log Backup

```bash
# Export cryptographic audit chain
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/audit/chain/export \
  > backups/audit_chain_$(date +%Y%m%d_%H%M%S).json

# Verify chain integrity before archiving
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/audit/chain/verify
```

### 3.4 Off-Site Backup

For production deployments, implement:

1. **Encrypted backup replication** to off-site storage
2. **Geographic redundancy** for federation scenarios
3. **Air-gapped backup** for encryption keys

---

## 4. Recovery Scenarios

### Scenario A: Single Container Failure

**Impact:** One service unavailable
**Recovery Time:** < 15 minutes

```bash
# Identify failed container
docker-compose ps

# Restart specific service
docker-compose restart <service_name>

# Or rebuild and restart
docker-compose up -d --build <service_name>
```

### Scenario B: Redis Data Corruption

**Impact:** Loss of agent state, keys, capabilities
**Recovery Time:** < 1 hour

```bash
# Stop the stack
docker-compose down

# Restore Redis data
docker volume rm telsonbase_redis_data
docker volume create telsonbase_redis_data
docker run --rm -v telsonbase_redis_data:/data \
  -v $(pwd)/backups:/backups alpine \
  cp /backups/dump.rdb /data/

# Restart
docker-compose up -d

# Verify restoration
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/agents/
```

### Scenario C: Complete System Loss

**Impact:** All services and data lost
**Recovery Time:** < 4 hours

**Step 1: Infrastructure Recovery**
```bash
# Clone repository
git clone https://github.com/quietfire/telsonbase.git
cd telsonbase

# Restore environment
cp /secure-backup/.env .env
```

**Step 2: Restore Encryption Keys**
```bash
# Restore from secure vault
export TelsonBase_ENCRYPTION_KEY="<from vault>"
export TelsonBase_ENCRYPTION_SALT="<from vault>"
```

**Step 3: Restore Redis Data**
```bash
# Copy backup to volume
mkdir -p ./redis-data
cp /backup-location/dump.rdb ./redis-data/
```

**Step 4: Start Services**
```bash
docker-compose up -d --build
```

**Step 5: Verify Recovery**
```bash
# Health check
curl http://localhost:8000/health

# Verify agents
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/agents/

# Verify audit chain
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/audit/chain/verify

# Verify federation
curl -H "X-API-Key: $API_KEY" http://localhost:8000/v1/federation/relationships
```

### Scenario D: Encryption Key Loss

**Impact:** Cannot decrypt stored secrets
**Recovery:** Requires re-initialization

This is a catastrophic scenario. Without encryption keys:
1. Encrypted secrets in Redis cannot be recovered
2. Agent signing keys must be regenerated
3. Federation trust must be re-established

**Prevention:**
- Store encryption keys in HSM or secure vault
- Maintain encrypted offline backup of keys
- Document key custodians

### Scenario E: Federation Partner Loss

**Impact:** Cannot communicate with federated instance
**Recovery Time:** Varies

```bash
# Check federation status
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/federation/relationships

# If partner is recoverable:
# - Wait for partner recovery
# - Re-verify mutual TLS

# If partner is permanently lost:
curl -X DELETE -H "X-API-Key: $API_KEY" \
  http://localhost:8000/v1/federation/relationships/{relationship_id}
```

---

## 5. Recovery Verification Checklist

After any recovery operation, verify:

- [ ] Health endpoint returns OK (`/health`)
- [ ] Authentication works (test API key)
- [ ] Agents are listed (`/v1/agents/`)
- [ ] Audit chain is valid (`/v1/audit/chain/verify`)
- [ ] Anomaly detection is active (`/v1/anomalies/dashboard/summary`)
- [ ] Federation relationships are intact (if applicable)
- [ ] Dashboard is accessible (`/dashboard`)
- [ ] MCP gateway is reachable (`curl http://localhost:8000/mcp` returns MCP endpoint response)

---

## 6. Backup Retention Policy

| Backup Type | Retention | Storage |
|-------------|-----------|---------|
| Hourly Redis snapshots | 24 hours | Local volume |
| Daily full backups | 30 days | Local + off-site |
| Weekly archives | 1 year | Off-site cold storage |
| Audit chain exports | 7 years | Compliance archive |

---

## 7. Testing Schedule

| Test | Frequency | Description |
|------|-----------|-------------|
| Backup verification | Weekly | Verify backup integrity |
| Container recovery | Monthly | Test single container restore |
| Full DR drill | Quarterly | Complete system recovery |
| Federation failover | Semi-annually | Test federation resilience |

---

## 8. Contact List

| Role | Responsibility | Contact |
|------|---------------|---------|
| DR Coordinator | Overall recovery coordination | TBD |
| Infrastructure Lead | Container/volume recovery | TBD |
| Security Lead | Key recovery, federation | TBD |
| Compliance Officer | Audit trail verification | TBD |

---

## 9. Documentation References

- [Security Architecture](SECURITY_ARCHITECTURE.md)
- [Incident Response](INCIDENT_RESPONSE.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
- [API Reference](API_REFERENCE.md)

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | J. Phillips | Initial release |
