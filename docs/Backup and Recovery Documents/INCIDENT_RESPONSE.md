# ClawCoat Incident Response Plan

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

---

## 1. Overview

This document defines the incident response procedures for TelsonBase deployments. It covers detection, classification, response, and recovery for security incidents involving the agent platform.

### Scope

This plan applies to:
- Agent compromise or anomalous behavior
- Unauthorized access attempts
- Data exfiltration attempts
- Federation trust breaches
- System availability incidents

---

## 2. Incident Classification

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **CRITICAL** | Immediate threat to system integrity or data | < 15 minutes | Active data exfiltration, compromised citizen agent, approval bypass |
| **HIGH** | Significant security risk requiring prompt action | < 1 hour | Capability probing, signature failures, suspicious federation activity |
| **MEDIUM** | Potential security issue requiring investigation | < 4 hours | Elevated anomaly counts, failed authentications, rate limit hits |
| **LOW** | Minor issue for awareness and monitoring | < 24 hours | Unusual patterns, minor policy violations |

### Automated Response Triggers

TelsonBase includes automated threat response. These actions are taken automatically:

| Indicator | Threat Level | Automatic Action |
|-----------|--------------|------------------|
| Critical anomaly burst (3+ in 5 min) | CRITICAL | Quarantine + Revoke delegations |
| Approval bypass attempt | CRITICAL | Immediate quarantine |
| Signature verification failures | CRITICAL | Quarantine + Revoke delegations |
| Capability probing (5+ in 10 min) | HIGH | Demote + Block external |
| Excessive failures (50%+ rate) | MEDIUM | Rate limit + Alert |

---

## 3. Detection

### Monitoring Points

1. **Anomaly Dashboard** (`/v1/anomalies/dashboard/summary`)
  - Real-time anomaly detection
  - Behavioral baseline deviations
  - Severity distribution

2. **Audit Chain** (`/v1/audit/chain/status`)
  - Tamper-evident logging
  - Chain integrity verification
  - Compliance export capability

3. **Threat Response** (`/v1/threats/recent`)
  - Automated threat detection
  - Response action history
  - Unresolved threat count

4. **Agent Trust Levels** (`/v1/system/reverification/status`)
  - Trust state monitoring
  - Promotion/demotion events
  - Re-verification failures

### Alert Channels

Configure alerts via:
- Goose/MCP polling via `list_pending_approvals` and `get_recent_audit_entries` tools
- Direct API polling
- Log aggregation (JSON format)

---

## 4. Response Procedures

### 4.1 CRITICAL Incident Response

**Immediate Actions (0-15 minutes):**

1. **Identify the affected agent(s)**
   ```bash
   curl -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/anomalies/dashboard/summary
   ```

2. **Manual quarantine if not auto-quarantined**
   ```bash
   curl -X POST -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/agents/{agent_id}/quarantine
   ```

3. **Revoke signing keys**
   ```bash
   curl -X POST -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/agents/{agent_id}/revoke \
     -d '{"reason": "Security incident", "revoked_by": "incident_response"}'
   ```

4. **Review recent activity**
   ```bash
   curl -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/audit/chain/entries?limit=100
   ```

5. **Check federation exposure**
   ```bash
   curl -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/federation/relationships
   ```

**Containment (15-60 minutes):**

1. Block external API access for affected agents
2. Review and revoke any active delegations
3. Check for lateral movement via delegation chains
4. Preserve audit logs for forensics
5. Notify relevant stakeholders

**Recovery (1-24 hours):**

1. Root cause analysis
2. Credential rotation (JWT keys, agent signing keys)
3. Re-register affected agents with new keys
4. Progressive trust restoration (QUARANTINE → PROBATION)
5. Update threat indicators if new pattern identified

### 4.2 HIGH Incident Response

**Initial Actions (0-60 minutes):**

1. Review anomaly details and evidence
2. Check if automated demotion occurred
3. Assess scope of potential compromise
4. Implement additional rate limiting if needed

**Investigation (1-4 hours):**

1. Analyze behavioral patterns
2. Check capability usage logs
3. Review approval request history
4. Verify federation message integrity

### 4.3 MEDIUM/LOW Incident Response

1. Log incident in tracking system
2. Review during next security review cycle
3. Adjust anomaly thresholds if needed
4. Update documentation if new pattern

---

## 5. Communication

### Internal Communication

| Severity | Notification | Channel |
|----------|--------------|---------|
| CRITICAL | Immediate | Direct contact, Slack/Teams |
| HIGH | Within 1 hour | Email + Slack |
| MEDIUM | Daily digest | Email |
| LOW | Weekly report | Dashboard |

### External Communication

For incidents affecting:
- **Federation partners**: Notify via secure channel within 1 hour for CRITICAL
- **Compliance stakeholders**: Document per SOC2/ISO27001 requirements
- **End users**: Only if data exposure confirmed

---

## 6. Post-Incident

### Required Documentation

1. **Incident Report**
  - Timeline of events
  - Systems affected
  - Actions taken
  - Root cause (if determined)

2. **Audit Export**
   ```bash
   curl -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/audit/chain/export \
     > incident_$(date +%Y%m%d)_audit.json
   ```

3. **Chain Verification**
   ```bash
   curl -H "X-API-Key: $API_KEY" \
     http://localhost:8000/v1/audit/chain/verify
   ```

### Lessons Learned

After each CRITICAL or HIGH incident:

1. Schedule post-mortem within 1 week
2. Identify process improvements
3. Update threat indicators if applicable
4. Update this document if procedures changed

---

## 7. Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Primary On-Call | TBD | 15 min no response |
| Security Lead | TBD | CRITICAL incidents |
| System Admin | TBD | Infrastructure issues |

---

## 8. Tool Reference

### Key API Endpoints for Incident Response

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/anomalies/dashboard/summary` | Anomaly overview |
| `GET /v1/anomalies/{anomaly_id}` | Specific anomaly details |
| `POST /v1/anomalies/{anomaly_id}/resolve` | Resolve anomaly |
| `GET /v1/threats/recent` | Recent threat events |
| `GET /v1/threats/stats` | Threat statistics |
| `POST /v1/agents/{id}/quarantine` | Quarantine agent |
| `POST /v1/agents/{id}/revoke` | Revoke signing key |
| `GET /v1/audit/chain/verify` | Verify log integrity |
| `GET /v1/audit/chain/export` | Export for compliance |
| `GET /v1/system/analyze` | Full security analysis |

### CLI Quick Reference

```bash
# Check system health
curl http://localhost:8000/health

# Get anomaly dashboard
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/anomalies/dashboard/summary

# Quarantine agent
curl -X POST -H "X-API-Key: $KEY" \
  http://localhost:8000/v1/agents/compromised_agent/quarantine

# Export audit for date range
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/v1/audit/chain/export?start_sequence=1000"

# Verify audit chain integrity
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/audit/chain/verify
```

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | J. Phillips | Initial release |
| 1.1 | Mar 8, 2026 | Quietfire AI | Version updated to v11.0.1 |

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
