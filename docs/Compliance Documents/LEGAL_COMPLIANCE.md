# ClawCoat - Legal & Regulatory Compliance Security Profile

**Version:** v11.0.1 · **Updated:** March 8, 2026 · **Maintainer:** Quietfire AI
**Platform:** Zero-Trust AI Agent Security Platform
**Target Markets:** Legal · Real Estate · Insurance · Accounting

---

## I. Executive Summary

TelsonBase is a self-hosted, zero-trust AI agent orchestration platform designed for industries where data sovereignty, auditability, and regulatory compliance are non-negotiable. The platform runs entirely on the customer's infrastructure - no data leaves the deployment, no client data is sent to third-party AI services for training, and all AI inference occurs locally via Ollama.

This document maps TelsonBase's security architecture to the compliance frameworks most commonly evaluated by real estate brokerages, law firms, and their respective regulatory bodies.

---

## II. Authentication & Access Control

### What Evaluators Look For

- How are users authenticated?
- Is multi-factor authentication supported and enforced?
- How are API keys and tokens managed?
- Can access be scoped and revoked?
- Are sessions time-limited?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Dual Authentication** | API Key (X-API-Key header) + JWT Bearer Token - both supported, both validated per request | `core/auth.py` |
| **API Key Security** | SHA-256 hashed storage, per-key scoped permissions, labels, owner tracking, zero-downtime rotation via key registry | `core/auth.py` |
| **JWT Tokens** | HS256 signed, configurable expiration (default 24h), unique JTI per token, Redis-backed revocation list with TTL auto-cleanup | `core/auth.py`, `core/config.py` |
| **Constant-Time Comparison** | `hmac.compare_digest()` used for all credential validation - prevents timing attacks | `core/auth.py` |
| **TOTP Multi-Factor Authentication** | RFC 6238 TOTP enrollment with QR provisioning URI, 10 one-time backup codes, replay-safe verification, role-based enforcement (Admin/Security Officer/Super Admin roles require MFA) | `core/mfa.py` |
| **Role-Based Access Control (RBAC)** | Five-tier role system (Viewer, Operator, Admin, Security Officer, Super Admin) with 24 granular permissions across 6 categories, custom per-user grants and denials | `core/rbac.py` |
| **Session Management** | Configurable duration (default 8 hours), automatic invalidation on user deactivation, unique session IDs via `uuid.uuid4()` | `core/rbac.py` |
| **Production Secret Validation** | Startup blocks if secrets use insecure defaults in production mode (`TELSONBASE_ENV=production`) | `core/config.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Logical access controls | SOC 2 CC6.1 | Implemented |
| User registration and authorization | SOC 2 CC6.2 | Implemented |
| Access removal on termination | SOC 2 CC6.3 | Implemented |
| Multi-factor authentication | SOC 2 CC6.1, ABA Formal Opinion 512, State Bar Ethics, Cyber Insurance | Implemented |
| Reasonable security measures | ABA Model Rule 1.6 | Implemented |
| Supervision of AI tools | ABA Model Rule 5.3 | Implemented (RBAC role enforcement) |

---

## III. Encryption

### What Evaluators Look For

- Is data encrypted at rest?
- Is data encrypted in transit?
- What algorithms and key lengths are used?
- How are encryption keys managed?
- Is key rotation supported?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Encryption at Rest** | AES-256-GCM with PBKDF2-derived keys (100,000 iterations), 96-bit random nonces per operation, authenticated encryption (GCM detects tampering) | `core/secure_storage.py` |
| **Automatic Field Encryption** | Eight sensitive field types auto-encrypted: signing_key, secret_key, api_key, token, password, private_key, session_key, encryption_key | `core/secure_storage.py` |
| **Versioned Ciphertext** | Format: `[version][nonce][ciphertext]` - enables future algorithm migration without re-encryption | `core/secure_storage.py` |
| **Encryption in Transit** | Traefik reverse proxy with Let's Encrypt ACME TLS certificates, HTTP-to-HTTPS redirect middleware | `docker-compose.yml` |
| **Federation mTLS** | Mutual TLS for cross-instance communication - RSA-4096 CA keys, RSA-2048 instance certificates, SHA-256 fingerprint pinning | `federation/mtls.py` |
| **Secret Management** | Docker secrets mounted at `/run/secrets/` (not visible in `docker inspect`), layered resolution: Docker secrets > environment variables > defaults | `core/config.py` |
| **Redis Authentication** | Password-protected Redis with `requirepass`, AOF persistence with `appendfsync everysec` | `docker-compose.yml` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Encryption at rest | SOC 2 CC6.7, ABA Rule 1.6, NAR Data Security | Implemented (AES-256-GCM) |
| Encryption in transit | SOC 2 CC6.7, NIST 800-53 SC-8 | Implemented (TLS 1.2+) |
| Key management | SOC 2 CC6.1 | Implemented (Docker secrets, PBKDF2) |

---

## IV. Audit Trail & Logging

### What Evaluators Look For

- Are all security-relevant events logged?
- Are logs tamper-evident or tamper-proof?
- Can logs be exported for auditor review?
- How long are logs retained?
- Can you demonstrate chain of custody?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Cryptographic Audit Chain** | SHA-256 hash-chained log entries - each entry contains the hash of the previous entry, creating a tamper-evident chain. If any entry is modified, the chain breaks on verification | `core/audit.py` |
| **47 Event Types Tracked** | Authentication (success/failure), task lifecycle, external requests, agent behavior, security alerts, capability enforcement, approvals, tool operations, system events | `core/audit.py` |
| **Chain Verification API** | Public endpoint `/v1/audit/chain/verify` validates chain integrity on demand | `main.py` |
| **Compliance Export** | `export_chain_for_compliance()` packages audit entries with verification metadata for auditor consumption | `core/audit.py` |
| **Monotonic Sequencing** | Each chain entry has a monotonically increasing sequence number - gaps are detectable | `core/audit.py` |
| **Per-Chain Identifiers** | Unique chain ID per instance lifetime for provenance tracking | `core/audit.py` |
| **Request Tracing** | Unique UUID assigned to every HTTP request for end-to-end correlation | `core/middleware.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Security event monitoring | SOC 2 CC7.2 | Implemented |
| Tamper-evident logging | SOC 2 CC7.2, eDiscovery (FRCP Rule 37(e)) | Implemented |
| Audit trail for data access | ABA Rule 1.6, RESPA | Implemented |
| Log retention (7 years) | SOC 2, Legal industry standard | Documented in DR plan |

---

## V. Network Security & Isolation

### What Evaluators Look For

- How is the network segmented?
- Which services are externally accessible?
- Are internal services isolated from external access?
- Is there rate limiting and DDoS protection?
- Are security headers configured?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Five Isolated Docker Networks** | frontend (public-facing), backend (application tier), data (database - internal only), ai (inference - internal only), monitoring (metrics - internal only) | `docker-compose.yml` |
| **Internal Network Enforcement** | Data, AI, and monitoring networks use `internal: true` - no external routing possible | `docker-compose.yml` |
| **Localhost-Bound Services** | Open-WebUI, Prometheus, Grafana bound to `127.0.0.1` - not reachable from external network. MCP gateway at `/mcp` is Bearer-token authenticated. | `docker-compose.yml` |
| **MQTT Authentication** | Mosquitto broker requires username/password, anonymous access disabled, no external port exposure | `monitoring/mosquitto/mosquitto.conf` |
| **Rate Limiting** | Token bucket algorithm - 300 requests/minute, burst 60, per-client tracking by API key or IP, stale bucket cleanup | `core/middleware.py` |
| **Per-Agent Rate Limiting** | Trust-level-based tiers: Quarantine (5/min), Probation (20/min), Resident (60/min), Citizen (120/min), System (unlimited). Action-cost multipliers (delete = 2x, external = 3x) | `core/rate_limiting.py` |
| **Security Headers** | X-Content-Type-Options: nosniff, X-Frame-Options: DENY, X-XSS-Protection: 1; mode=block, Referrer-Policy: strict-origin-when-cross-origin, server header stripped | `core/middleware.py` |
| **Request Size Limiting** | Configurable max body size (default 10MB) | `core/middleware.py` |
| **CORS Restrictions** | Explicit origin allowlist (no wildcard), credentials only with named origins, restricted methods and headers | `core/config.py`, `main.py` |
| **Egress Firewall** | All outbound API calls filtered through domain whitelist - default: api.anthropic.com, api.perplexity.ai, api.venice.ai only | `gateway/egress_proxy.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Network segmentation | SOC 2 CC6.6 | Implemented |
| Protection against external threats | SOC 2 CC6.6 | Implemented |
| Rate limiting / abuse prevention | SOC 2 CC7.1 | Implemented |

---

## VI. Data Sovereignty & Privacy

### What Evaluators Look For

- Where does data reside?
- Does data leave the deployment environment?
- Is client data used to train AI models?
- Can data be classified by sensitivity?
- Can data be deleted on request?
- Are retention policies configurable?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Self-Hosted Architecture** | Entire platform runs on customer infrastructure - Docker Compose orchestration on customer-owned hardware | `docker-compose.yml` |
| **Local AI Inference** | Ollama runs locally on the `ai` network (internal only) - no data sent to external AI APIs for inference or training | `docker-compose.yml` |
| **Data Sovereignty Score** | Calculated score (0-100) factoring LLM locality (35%), data residency (25%), network exposure (20%), backup sovereignty (10%), auth posture (10%) | `core/system_analysis.py` |
| **Data Classification** | Four-tier system: PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED (attorney-client privilege level). Auto-classification rules based on data type and tenant type (law firms default to CONFIDENTIAL) | `core/data_classification.py` |
| **Data Retention Engine** | Configurable per-tenant retention policies, automated expiry detection, CCPA-compliant deletion request workflow (pending > approved > executing > completed), legal hold integration (deletion blocked when hold active) | `core/data_retention.py` |
| **Right to Deletion** | Full deletion workflow with approval gate, audit trail of what was deleted (without retaining the data itself), automatic hold check before execution | `core/data_retention.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Data residency / sovereignty | ABA Rule 1.6, ABA Formal Opinion 512, GDPR Art. 44-49 | Implemented (self-hosted) |
| No third-party AI training | ABA Formal Opinion 512, State Bar Ethics Opinions (all states) | Implemented (local Ollama) |
| Data classification | SOC 2 CC6.7, ABA Rule 1.6 | Implemented |
| Right to deletion | CCPA, CPRA, 15+ state privacy laws | Implemented |
| Data retention policies | RESPA (3-5 year records), SOC 2 Privacy Criteria | Implemented |
| Data minimization | NAR Data Security Toolkit, CCPA | Implemented (retention engine) |

---

## VII. Multi-Tenancy & Client-Matter Isolation

### What Evaluators Look For

- Is data isolated between clients/tenants?
- Can ethical walls be enforced technically?
- Is there per-tenant access control?
- Can tenant data be independently managed (exported, deleted)?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Tenant Model** | Organization-level isolation with tenant type classification (law_firm, insurance, real_estate, healthcare, small_business, personal, general), per-tenant configuration overrides, automatic data classification defaults | `core/tenancy.py` |
| **Client-Matter Hierarchy** | Data organized within tenants by client matter - supports transaction, litigation, and client_file types with lifecycle management (active > closed > hold) | `core/tenancy.py` |
| **Redis Key Namespacing** | `tenant_scoped_key()` utility generates `tenant:{id}:{key}` prefixed keys - all data operations scoped to tenant context | `core/tenancy.py` |
| **Tenant Context** | Lightweight request-scoping object (tenant_id, user_id, matter_id) passed through request handling for enforcement | `core/tenancy.py` |
| **Litigation Hold on Matters** | Individual matters can be placed on hold, preventing closure or data deletion | `core/tenancy.py`, `core/legal_hold.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Client data isolation | ABA Rule 1.6, ABA Rule 1.7 (conflicts) | Implemented |
| Ethical walls / information barriers | ABA Rule 1.10 (imputed conflicts) | Implemented (matter-level isolation) |
| MLS data separation | NAR MLS Data Security Requirements | Implemented (tenant scoping) |
| Transaction data separation | RESPA Section 8 | Implemented |
| Logical access between tenants | SOC 2 CC6.1, CC6.7 | Implemented |

---

## VIII. Legal Hold & eDiscovery Readiness

### What Evaluators Look For

- Can data be preserved when litigation is anticipated?
- Does preservation override retention-based deletion?
- Is there a custodian notification and acknowledgment workflow?
- Can holds be released with proper authorization and audit trail?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Legal Hold System** | Full lifecycle management - create, enforce, release with audit trail at every step | `core/legal_hold.py` |
| **Scope Control** | Holds can target specific matters or entire tenants, covering specific data types (all, communications, documents, transactions) | `core/legal_hold.py` |
| **Deletion Override** | Active holds block all retention-based and manual deletion - `is_data_held()` checked before any data destruction | `core/legal_hold.py`, `core/data_retention.py` |
| **Custodian Management** | Track which users have been notified of a hold, record timestamped acknowledgments, report unacknowledged custodians | `core/legal_hold.py` |
| **Release Authorization** | Hold release requires Security Officer or Super Admin role, full audit details recorded including release reason | `core/legal_hold.py` |
| **Tamper-Evident Audit** | All hold activities (creation, custodian addition, acknowledgment, release) logged to the cryptographic audit chain | `core/legal_hold.py`, `core/audit.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| ESI preservation obligation | FRCP Rule 37(e) | Implemented |
| Litigation hold enforcement | Zubulake v. UBS Warburg doctrine | Implemented |
| Ethical duty to preserve | ABA Model Rules | Implemented |
| Hold notification tracking | State eDiscovery Rules | Implemented |
| Hold override of retention | FRCP, state eDiscovery | Implemented |

---

## IX. Incident Response & Breach Notification

### What Evaluators Look For

- Is there a documented incident response plan?
- How are breaches assessed and classified?
- Can notification deadlines be tracked?
- Are notification activities auditable?
- What are the recovery time objectives?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Incident Response Plan** | Four severity levels (Critical 15min / High 1hr / Medium 4hr / Low 24hr), automated threat response triggers, step-by-step procedures, communication templates | `docs/INCIDENT_RESPONSE.md` |
| **Breach Assessment Engine** | Severity classification (Critical/High/Medium/Low), affected tenant tracking, data type exposure analysis, containment status progression | `core/breach_notification.py` |
| **Auto Notification Determination** | Rules engine maps exposed data types to notification requirements: SSN (required, 30 days), financial (required, 60 days), PII (required, 60 days), privileged (required, 30 days), medical (required, 60 days) | `core/breach_notification.py` |
| **Notification Tracking** | Per-recipient records (regulator, affected individual, tenant, law enforcement) with method, send status, and acknowledgment tracking | `core/breach_notification.py` |
| **Overdue Detection** | `get_overdue_notifications()` identifies assessments past their notification deadline with pending notifications - for scheduled alerting | `core/breach_notification.py` |
| **Disaster Recovery** | RTO < 4 hours, RPO < 1 hour, MTTR < 2 hours. Backup retention: hourly snapshots (24h), daily (30d), weekly (1y), audit chains (7y) | `docs/DISASTER_RECOVERY.md` |
| **Automated Threat Response** | Critical threats trigger automatic agent quarantine, key revocation, and rate limiting escalation | `core/threat_response.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Incident response procedures | SOC 2 CC7.3, CC7.4 | Implemented |
| Breach notification (all 50 states) | State breach notification laws (30-72 day deadlines) | Implemented |
| Client notification of unauthorized disclosure | ABA Model Rule 1.4 | Implemented |
| Notification deadline tracking | State laws, cyber insurance requirements | Implemented |
| Business continuity / DR | SOC 2, vendor risk management | Documented |

---

## X. Agent Security & AI Governance

### What Evaluators Look For

- How are AI agents sandboxed?
- Can agents access data beyond their scope?
- Are agent actions auditable?
- Is there human oversight of AI decisions?
- How is agent trust established?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Capability-Based Sandboxing** | Each agent declares capabilities (filesystem scope, allowed domains, MQTT topics, inter-agent access). Access beyond declared capabilities is denied and audit-logged | `core/capabilities.py` |
| **Human-in-the-Loop (HITL) Gates** | Sensitive operations pause for human authorization - new external domains, file deletions, anomaly-flagged actions all require approval before execution | `core/approval.py` |
| **Agent Trust Levels** | Five-tier progression: Quarantine > Probation > Resident > Citizen > Agent. Automatic promotion based on behavior, automatic demotion on violations | `core/trust_levels.py` |
| **Behavioral Anomaly Detection** | Six anomaly types monitored: rate spikes, new resources, new actions, unusual timing, enumeration patterns, error spikes | `core/anomaly.py` |
| **Cryptographic Message Signing** | HMAC-SHA256 signing of all inter-agent messages, 5-minute replay window, constant-time signature comparison | `core/signing.py` |
| **QMS™ Protocol** | Qualified Message Standard (QMS™) v2.1.6 - all agent communication follows structured formatting with provenance tracking | `core/qms.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Supervision of AI / nonlawyer assistance | ABA Model Rule 5.3 | Implemented (HITL gates, trust levels) |
| AI tool oversight | ABA Formal Opinion 512 | Implemented |
| Audit trail of AI actions | SOC 2 CC7.2, ABA Rule 1.6 | Implemented |
| Prevention of unauthorized AI actions | SOC 2 CC6.1 | Implemented (capabilities, approval gates) |

---

## XI. Compliance Reporting

### What Evaluators Look For

- Can compliance posture be assessed on demand?
- Is there a framework for SOC 2 evidence?
- Can reports be exported for auditors?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **SOC 2 Control Mapping** | 10 Trust Service Criteria controls defined (CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC7.1, CC7.2, CC7.3, CC7.4, CC8.1) with evidence requirements per control | `core/compliance.py` |
| **Evidence Collection Framework** | Registered evidence collectors per control, automated assessment scoring, compliance percentage calculation | `core/compliance.py` |
| **Report Generation** | JSON export of compliance posture with per-control assessment details and audit logging of report generation events | `core/compliance.py` |
| **Multi-Framework Support** | Architecture supports SOC 2, ISO 27001, and NIST frameworks (SOC 2 controls populated, others extensible) | `core/compliance.py` |

---

## XII. Evaluator Quick Reference - Regulation-to-Feature Map

### For Real Estate Evaluators

| Regulation | TelsonBase Feature | Status |
|-----------|-------------------|--------|
| Fair Housing Act | Tenant isolation prevents cross-client data leakage, data classification, audit trail | Implemented |
| RESPA | Transaction data isolation via client-matter model, 3-5 year retention support, access audit trail | Implemented |
| NAR Data Security Toolkit | Encryption (AES-256-GCM), MFA, audit logging, data sovereignty (self-hosted), access controls | Implemented |
| MLS Data Security | Tenant-scoped data isolation, encryption at rest, access controls, no external data sharing | Implemented |
| State Privacy Laws (CCPA + 15 states) | Right to deletion workflow, data retention policies, breach notification, data classification | Implemented |
| SOC 2 Type II | Control framework, evidence collection architecture, continuous monitoring support | Framework implemented |

### For Legal Evaluators

| Regulation | TelsonBase Feature | Status |
|-----------|-------------------|--------|
| ABA Rule 1.6 (Confidentiality) | AES-256-GCM encryption, RBAC, MFA, audit trail, self-hosted (no third-party AI training), data classification (RESTRICTED level for privilege) | Implemented |
| ABA Rule 1.7 / 1.10 (Conflicts) | Client-matter isolation, tenant scoping, ethical wall support via matter-level access control | Implemented |
| ABA Rule 5.3 (AI Supervision) | HITL approval gates, agent trust levels, capability sandboxing, behavioral anomaly detection | Implemented |
| ABA Formal Opinion 512 | Self-hosted AI (data never sent externally), encryption, access controls, audit trail, MFA | Implemented |
| FRCP Rule 37(e) (eDiscovery) | Legal hold system, deletion override, custodian tracking, tamper-evident audit chain | Implemented |
| State Bar Ethics Opinions | Self-hosted architecture, encryption, MFA, vendor audit trail, data classification | Implemented |
| SOC 2 Type II | Control framework with evidence collection | Framework implemented |
| State Breach Notification | Automated severity assessment, notification requirement determination, deadline tracking | Implemented |

---

## XIII. Architecture Diagram - Security Layers

```
                    INTERNET
                       |
              [Traefik - TLS/HTTPS]     Port 80/443 only
                       |
            +----- FRONTEND NETWORK -----+
            |          |                 |
      [/mcp]    [Open-WebUI]    [MCP Server]     <-- localhost-bound except MCP
            |                         |    |
            |              +--- BACKEND NETWORK ---+
            |              |          |            |
            |          [Worker]    [Beat]    [Prometheus]
            |              |          |            |
            |    +---- DATA NETWORK (internal) ----+
            |    |         |                       |
            | [Redis]  [Mosquitto]                 |
            |  (auth)    (auth)                    |
            |                                      |
            +------ AI NETWORK (internal) ---------+
            |              |                       |
         [Ollama]    [MCP Server]            [MONITORING]
        (local LLM)  (bridges all)        [Prometheus/Grafana]
                                           (internal only)
```

---

## XIV. Security Contact & Vulnerability Reporting

- **Security Policy:** `SECURITY.md` in project root
- **Vulnerability Reporting:** Responsible disclosure process documented
- **Response Times:** Critical (24h), High (7d), Medium (30d), Low (next release)
- **Contact:** support@clawcoat.com

---

*This document is intended for compliance evaluators, security auditors, and enterprise procurement teams assessing TelsonBase for deployment in regulated industries. For technical implementation details, refer to the referenced source files.*

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
