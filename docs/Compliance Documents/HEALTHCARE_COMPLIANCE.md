# ClawCoat - Healthcare Compliance Security Profile (HIPAA/HITECH/HITRUST)

**Version:** v11.0.1 · **Updated:** March 8, 2026 · **Maintainer:** Quietfire AI
**Platform:** Zero-Trust AI Agent Security Platform
**Target Markets:** Healthcare · Legal · Insurance · Real Estate · Accounting

---

## I. Executive Summary

TelsonBase is a self-hosted, zero-trust AI agent orchestration platform currently deployed for real estate and legal professionals. This document is forward-looking - it maps TelsonBase's existing and extended security infrastructure to the HIPAA Security Rule (45 CFR Part 164), the HITECH Act, and the HITRUST Common Security Framework (CSF).

**TelsonBase is not currently deployed in healthcare environments and does not process Protected Health Information (PHI) in production.** This document demonstrates that the architectural controls, administrative safeguards, and technical mechanisms required for HIPAA compliance are already in place or pre-mapped within the platform. All healthcare-specific controls layer on top of - and do not conflict with - the existing real estate and legal compliance infrastructure documented in `LEGAL_COMPLIANCE.md`.

When and if TelsonBase pursues healthcare as a target market, the transition will be a configuration exercise rather than an architectural overhaul. Every module referenced in this document exists in the codebase today.

---

## II. Authentication & Access Control

### What Evaluators Look For

- Are unique user identifiers enforced for every user?
- Is multi-factor authentication supported and enforceable?
- Are role-based access controls granular enough for healthcare workflows?
- Do sessions automatically terminate after inactivity?
- Is there an emergency access ("break-the-glass") procedure?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **TOTP Multi-Factor Authentication** | RFC 6238 TOTP enrollment with QR provisioning URI, 10 one-time backup codes, replay-safe verification, role-based enforcement - MFA required for any role with PHI access | `core/mfa.py` |
| **Role-Based Access Control (RBAC)** | Five-tier role system (Viewer, Operator, Admin, Security Officer, Super Admin) with 24 granular permissions across 6 categories, custom per-user grants and denials, PHI access restricted to explicitly authorized roles | `core/rbac.py` |
| **Session Management with Auto-Logoff** | Configurable session duration (default 8 hours, HIPAA-recommended 15 minutes for PHI workstations), automatic invalidation on inactivity timeout, automatic invalidation on user deactivation, unique session IDs via `uuid.uuid4()` | `core/session_management.py` |
| **Unique User Identification** | Every action attributed to a specific ActorType (human, ai_agent, system, service_account, emergency) with unique actor ID - no shared or generic accounts permitted, all access individually auditable | `core/audit.py` |
| **Break-the-Glass Emergency Access** | Emergency access procedure for time-critical PHI access when normal authorization is unavailable - requires post-access justification, Security Officer review, full audit trail of all actions taken during emergency session, automatic expiration | `core/emergency_access.py` |
| **Constant-Time Credential Comparison** | `hmac.compare_digest()` used for all credential validation - prevents timing attacks against authentication tokens | `core/auth.py` |
| **Production Secret Validation** | Startup blocks if secrets use insecure defaults in production mode (`TELSONBASE_ENV=production`) | `core/config.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Unique user identification | HIPAA §164.312(a)(2)(i) | Implemented |
| Emergency access procedure | HIPAA §164.312(a)(2)(ii) | Implemented |
| Automatic logoff | HIPAA §164.312(a)(2)(iii) | Implemented |
| Access control and authorization | HIPAA §164.312(a)(1) | Implemented |
| Multi-factor authentication | HIPAA §164.312(d), HITRUST 01.b | Implemented |
| Role-based access | HIPAA §164.312(a)(1), NIST 800-66 | Implemented |

---

## III. PHI Protection & Privacy

### What Evaluators Look For

- Is there a mechanism for tracking disclosures of PHI?
- Is the minimum necessary standard enforced?
- Can PHI be de-identified per Safe Harbor or Expert Determination?
- Is data classified by sensitivity level, including a tier for PHI/RESTRICTED data?
- Are policies configurable per covered entity or business associate?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **PHI Disclosure Accounting** | Full disclosure tracking with recipient, purpose, date, data elements disclosed, legal authority (TPO, authorization, required by law, public health, research). Supports individual right to an accounting of disclosures covering the prior 6 years. Exportable reports for HHS inquiries | `core/phi_disclosure.py` |
| **Minimum Necessary Standard** | Policy engine enforcing minimum necessary access - each role and request type mapped to the minimum PHI fields required. Bulk access requests automatically flagged for review. Override requires documented justification and Security Officer approval | `core/minimum_necessary.py` |
| **PHI De-identification (Safe Harbor)** | Automated Safe Harbor de-identification removing all 18 HIPAA identifiers: names, geographic data below state, dates (except year) for ages >89, phone/fax numbers, email, SSN, MRN, health plan numbers, account numbers, certificate/license numbers, VINs, device IDs, URLs, IPs, biometrics, photographs, any unique identifier. Verification that no residual identifiers remain | `core/phi_deidentification.py` |
| **Four-Tier Data Classification** | PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED. PHI automatically classified as RESTRICTED. Auto-classification rules based on data type and tenant type - healthcare tenants default to CONFIDENTIAL, PHI fields escalated to RESTRICTED. Classification enforces encryption, access control, and audit requirements per tier | `core/data_classification.py` |
| **Tenant-Aware Privacy Policies** | Per-tenant configuration overrides support varying privacy requirements across covered entities and business associates within the same deployment | `core/tenancy.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Accounting of disclosures | HIPAA §164.528 | Implemented |
| Minimum necessary standard | HIPAA §164.502(b), §164.514(d) | Implemented |
| De-identification (Safe Harbor) | HIPAA §164.514(b)(2) | Implemented |
| Right of access to PHI | HIPAA §164.524 | Implemented (data export) |
| Data classification | NIST 800-66, HITRUST 07.a | Implemented |

---

## IV. Encryption & Data Integrity

### What Evaluators Look For

- Is PHI encrypted at rest with NIST-approved algorithms?
- Is PHI encrypted in transit?
- Are encryption keys managed securely with documented rotation?
- Is data integrity verified to detect tampering?
- Does encryption meet the HIPAA Breach Notification Safe Harbor?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Encryption at Rest (AES-256-GCM)** | AES-256-GCM with PBKDF2-derived keys (100,000 iterations), 96-bit random nonces per operation, authenticated encryption (GCM tag detects any tampering). Meets HIPAA encryption safe harbor - encrypted PHI is not considered "unsecured PHI" under breach notification rules | `core/secure_storage.py` |
| **HMAC-SHA256 Integrity Verification** | All stored PHI records include HMAC-SHA256 integrity tags computed over the plaintext. Integrity verified on every read - any modification detected and flagged as a security event. Separate integrity key from encryption key | `core/secure_storage.py` |
| **Encryption in Transit (TLS 1.2+)** | Traefik reverse proxy with Let's Encrypt ACME TLS certificates, HTTP-to-HTTPS redirect middleware, minimum TLS 1.2 enforced. All PHI in transit encrypted per NIST SP 800-52 | `docker-compose.yml` |
| **PBKDF2 Key Derivation** | 100,000 iteration PBKDF2 with SHA-256 for deriving encryption keys from master secrets - meets NIST SP 800-132 recommendations | `core/secure_storage.py` |
| **Versioned Ciphertext Format** | Format: `[version][nonce][ciphertext]` - enables future algorithm migration without bulk re-encryption | `core/secure_storage.py` |
| **Automatic Field Encryption** | Eight sensitive field types auto-encrypted: signing_key, secret_key, api_key, token, password, private_key, session_key, encryption_key. PHI fields added to auto-encryption when healthcare module enabled | `core/secure_storage.py` |
| **Secret Management** | Docker secrets mounted at `/run/secrets/` (not visible in `docker inspect`), layered resolution: Docker secrets > environment variables > defaults | `core/config.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Encryption at rest | HIPAA §164.312(a)(2)(iv) | Implemented (AES-256-GCM) |
| Encryption in transit | HIPAA §164.312(e)(1) | Implemented (TLS 1.2+) |
| Integrity controls | HIPAA §164.312(c)(1) | Implemented (HMAC-SHA256) |
| Encryption safe harbor | HITECH §13402(h) | Implemented (NIST-approved) |
| Key management | NIST 800-66, HITRUST 10.f | Implemented (Docker secrets, PBKDF2) |

---

## V. Audit Trail & Accountability

### What Evaluators Look For

- Are all accesses to PHI logged?
- Are audit logs tamper-evident or tamper-proof?
- Can logs identify who accessed what PHI, when, and why?
- Are AI agent actions independently auditable?
- Can logs be exported for HHS investigation or compliance review?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **SHA-256 Hash-Chained Audit Log** | Every log entry contains the SHA-256 hash of the previous entry, creating a tamper-evident chain. If any entry is modified, inserted, or deleted, the chain breaks on verification. Meets forensic evidence standards | `core/audit.py` |
| **ActorType Enumeration** | Five actor types tracked: `human`, `ai_agent`, `system`, `service_account`, `emergency`. Every audit entry attributes the action to a specific actor type and unique actor ID - critical for distinguishing human vs. AI access to PHI | `core/audit.py` |
| **47 Event Types Tracked** | Authentication (success/failure), task lifecycle, external requests, agent behavior, security alerts, capability enforcement, approvals, tool operations, system events, PHI access, PHI disclosure, emergency access | `core/audit.py` |
| **JSON Structured Logging** | All audit entries stored as structured JSON with consistent schema: timestamp, actor_type, actor_id, event_type, resource, outcome, metadata. Machine-parseable for automated compliance analysis and SIEM integration | `core/audit.py` |
| **Tamper Detection via Chain Verification** | Public endpoint `/v1/audit/chain/verify` validates chain integrity on demand. `export_chain_for_compliance()` packages audit entries with verification metadata for HHS or auditor consumption | `core/audit.py` |
| **Monotonic Sequencing** | Each chain entry has a monotonically increasing sequence number - gaps are detectable and flagged | `core/audit.py` |
| **Request Tracing** | Unique UUID assigned to every HTTP request for end-to-end correlation across services | `core/middleware.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Audit controls | HIPAA §164.312(b) | Implemented |
| Information system activity review | HIPAA §164.308(a)(1)(ii)(D) | Implemented |
| Tamper-evident logging | HIPAA §164.312(c)(2), HITRUST 09.aa | Implemented |
| Log retention (6 years minimum) | HIPAA §164.530(j) | Documented (7-year retention) |
| Audit trail for PHI access | HITECH §13405(c) | Implemented |

---

## VI. Administrative Safeguards

### What Evaluators Look For

- Is there a sanctions policy for workforce violations?
- Are security awareness and training programs documented?
- Is there a contingency plan with regular testing?
- Are Business Associate Agreements tracked and managed?
- Is there a breach notification process with regulatory timelines?
- Are data retention and legal hold policies enforced?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Sanctions Tracking** | Workforce sanctions policy engine - tracks violations by user, severity (warning, suspension, termination, report_to_authority), violation type (unauthorized_access, phi_misuse, policy_violation, training_noncompliance, device_loss), resolution status, and appeal process. Sanction history maintained per user for pattern detection | `core/sanctions.py` |
| **Security Awareness Training** | Training program management with module tracking (HIPAA Privacy, HIPAA Security, PHI Handling, Breach Reporting, Password Security, Social Engineering, Device Security, Incident Response), completion status per user, annual recertification enforcement, overdue training detection and escalation | `core/training.py` |
| **Contingency Plan Testing** | Scheduled contingency plan tests with type classification (tabletop, simulation, full_failover, backup_restore, communication), pass/fail tracking, findings documentation, remediation tracking. Annual testing cadence enforcement per HIPAA §164.308(a)(7) | `core/contingency_testing.py` |
| **BAA Tracking** | Business Associate Agreement lifecycle management - tracks BAA status (draft, active, terminated, expired), counterparty details, effective/expiration dates, amendment history, required security provisions verification, annual review enforcement | `core/baa_tracking.py` |
| **Breach Notification** | Severity classification (Critical/High/Medium/Low), affected individual count, data type exposure analysis (SSN, financial, PII, PHI, privileged), notification requirement determination with regulatory deadlines (HHS 60 days, individuals 60 days, media if >500 affected), notification tracking per recipient | `core/breach_notification.py` |
| **Data Retention with Legal Hold** | Configurable per-tenant retention policies, automated expiry detection, HIPAA 6-year minimum retention enforcement for designated record sets, legal hold integration - deletion blocked when hold active, right-to-amendment workflow support | `core/data_retention.py`, `core/legal_hold.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Sanctions policy | HIPAA §164.308(a)(1)(ii)(C) | Implemented |
| Security awareness and training | HIPAA §164.308(a)(5) | Implemented |
| Contingency plan | HIPAA §164.308(a)(7) | Implemented |
| Contingency plan testing | HIPAA §164.308(a)(7)(ii)(D) | Implemented |
| Business associate contracts | HIPAA §164.308(b), §164.314(a) | Implemented |
| Breach notification (individuals) | HITECH §13402(a), HIPAA §164.404 | Implemented |
| Breach notification (HHS) | HITECH §13402(b), HIPAA §164.408 | Implemented |
| Breach notification (media) | HIPAA §164.406 | Implemented (>500 threshold) |
| Data retention (6-year minimum) | HIPAA §164.530(j) | Implemented |
| Legal hold / preservation | FRCP Rule 37(e), HIPAA investigations | Implemented |

---

## VII. Technical Safeguards

### What Evaluators Look For

- Is the network segmented to isolate PHI from general traffic?
- Are sessions terminated after inactivity?
- Are database and message broker services authenticated and isolated?
- Are security headers and CORS policies hardened?
- Is the administrative interface secured against unauthorized access?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Five Isolated Docker Networks** | frontend (public-facing), backend (application tier), data (database - internal only), ai (inference - internal only), monitoring (metrics - internal only). PHI processing restricted to backend and data networks only | `docker-compose.yml` |
| **Internal Network Enforcement** | Data, AI, and monitoring networks use `internal: true` - no external routing possible. PHI data stores exist exclusively on the internal data network | `docker-compose.yml` |
| **Automatic Logoff** | Configurable inactivity timeout with HIPAA-recommended defaults. Sessions automatically invalidated after inactivity threshold. Workstation-type awareness for stricter timeout on shared terminals | `core/session_management.py` |
| **Redis Authentication + AOF Persistence** | Password-protected Redis with `requirepass`, AOF persistence with `appendfsync everysec` ensuring PHI cached in Redis is not lost on restart. Redis bound to internal data network only | `docker-compose.yml` |
| **MQTT Authentication** | Mosquitto broker requires username/password, anonymous access disabled, no external port exposure. PHI-related event topics restricted by ACL | `monitoring/mosquitto/mosquitto.conf` |
| **CORS Hardened** | Explicit origin allowlist (no wildcard), credentials only with named origins, restricted methods and headers. Prevents cross-origin PHI exfiltration | `core/config.py`, `main.py` |
| **Traefik Dashboard Disabled** | Administrative dashboard disabled in production - no web-based management interface exposed. Reduces attack surface for infrastructure hosting PHI | `docker-compose.yml` |
| **Security Headers** | X-Content-Type-Options: nosniff, X-Frame-Options: DENY, X-XSS-Protection: 1; mode=block, Referrer-Policy: strict-origin-when-cross-origin, server header stripped | `core/middleware.py` |
| **Egress Firewall** | All outbound API calls filtered through domain whitelist - prevents PHI exfiltration via unauthorized external endpoints | `gateway/egress_proxy.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Access control (technical) | HIPAA §164.312(a)(1) | Implemented |
| Automatic logoff | HIPAA §164.312(a)(2)(iii) | Implemented |
| Transmission security | HIPAA §164.312(e)(1) | Implemented (TLS 1.2+) |
| Integrity controls | HIPAA §164.312(c)(1) | Implemented |
| Facility access controls (logical) | HIPAA §164.310(a)(1) | Implemented (network segmentation) |
| Workstation security | HIPAA §164.310(c) | Implemented (auto-logoff, headers) |

---

## VIII. HITRUST CSF Alignment

### What Evaluators Look For

- Are security controls mapped to HITRUST CSF domains?
- Is there a baseline set of controls pre-mapped?
- Can risk assessments be tracked and scored?
- Is compliance posture reportable on demand?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **12 HITRUST CSF Domains Tracked** | Information Protection Program (01), Endpoint Protection (02), Portable Media Security (03), Mobile Device Security (04), Wireless Security (05), Configuration Management (06), Vulnerability Management (07), Network Protection (08), Transmission Protection (09), Password Management (10), Access Control (11), Audit Logging & Monitoring (12) | `core/hitrust_controls.py` |
| **17 Baseline Controls Pre-Mapped** | Controls mapped from TelsonBase modules to HITRUST requirements: MFA (01.b), RBAC (01.c), encryption at rest (06.d), encryption in transit (09.m), audit logging (09.aa), session management (01.t), data classification (07.a), breach notification (11.a), contingency testing (12.c), BAA tracking (05.i), sanctions (02.e), training (02.e), network segmentation (09.m), PHI de-identification (07.c), minimum necessary (01.d), emergency access (01.b), integrity verification (09.s) | `core/hitrust_controls.py` |
| **Risk Assessment Tracking** | Per-control risk assessment with inherent risk, residual risk, control effectiveness scoring (0-100), risk owner assignment, review date tracking, remediation plan linkage | `core/hitrust_controls.py` |
| **Compliance Posture Reporting** | On-demand HITRUST readiness report with domain-level and control-level scoring, gap analysis, evidence mapping, exportable JSON format for assessor consumption | `core/hitrust_controls.py` |

### HITRUST CSF Domain Mapping

| HITRUST Domain | TelsonBase Controls | Readiness |
|----------------|-------------------|-----------|
| 01 - Information Protection Program | Data classification, retention, legal hold, PHI handling policies | Pre-Mapped |
| 02 - Endpoint Protection | Session management, auto-logoff, security headers | Pre-Mapped |
| 03 - Portable Media Security | Encryption at rest (AES-256-GCM), data classification | Pre-Mapped |
| 04 - Mobile Device Security | Token-based auth, session timeout, MFA enforcement | Pre-Mapped |
| 05 - Wireless Security | Network segmentation, internal-only networks | Pre-Mapped |
| 06 - Configuration Management | Docker Compose declarative config, production secret validation | Pre-Mapped |
| 07 - Vulnerability Management | Egress firewall, rate limiting, anomaly detection | Pre-Mapped |
| 08 - Network Protection | Five Docker networks, internal enforcement, CORS, security headers | Pre-Mapped |
| 09 - Transmission Protection | TLS 1.2+, HMAC-SHA256 message signing, mTLS federation | Pre-Mapped |
| 10 - Password Management | PBKDF2 key derivation, SHA-256 hashed API keys, TOTP MFA | Pre-Mapped |
| 11 - Access Control | RBAC, capability sandboxing, trust levels, emergency access | Pre-Mapped |
| 12 - Audit Logging & Monitoring | SHA-256 hash-chained audit, 47 event types, chain verification | Pre-Mapped |

---

## IX. Agent Security (AI-Specific)

### What Evaluators Look For

- How are AI agents prevented from accessing PHI beyond their scope?
- Is there human oversight of AI decisions involving PHI?
- Are AI agent actions on PHI independently auditable?
- How is trust established and maintained for AI agents?
- Are inter-agent messages validated and authenticated?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Agent Trust Levels** | Five-tier progression: Quarantine > Probation > Resident > Citizen > Agent. Agents handling PHI require minimum Resident trust level. Automatic demotion on policy violations. PHI access capability requires explicit grant - never inherited from trust level alone | `core/trust_levels.py` |
| **Human-in-the-Loop (HITL) Approval Gates** | All PHI disclosure, PHI export, and PHI de-identification operations require human approval before execution. Configurable approval timeout with automatic denial on expiry. Approval audit trail with approver identity and justification | `core/approval.py` |
| **Capability-Based Sandboxing** | Each agent declares capabilities (filesystem scope, allowed domains, MQTT topics, inter-agent access). PHI access is a distinct capability - agents without PHI capability cannot read, write, or process PHI regardless of trust level. Unauthorized attempts audit-logged and trigger anomaly detection | `core/capabilities.py` |
| **QMS™ Message Validation** | Qualified Message Standard (QMS™) v2.1.6 - all agent communication follows structured formatting with provenance tracking. Messages containing PHI flagged and routed through encrypted channels only. Message schema validation prevents PHI leakage via malformed messages | `core/qms.py` |
| **Behavioral Anomaly Detection** | Six anomaly types monitored: rate spikes, new resources, new actions, unusual timing, enumeration patterns, error spikes. PHI-specific anomaly rules: bulk PHI access detection, after-hours PHI access alerting, PHI access frequency deviation from baseline | `core/anomaly.py` |
| **Cryptographic Message Signing** | HMAC-SHA256 signing of all inter-agent messages, 5-minute replay window, constant-time signature comparison. Prevents message forgery that could trick agents into unauthorized PHI disclosure | `core/signing.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Access control for AI/automated processes | HIPAA §164.312(a)(1) | Implemented |
| Audit trail of AI actions on PHI | HIPAA §164.312(b), HITECH §13405(c) | Implemented |
| Minimum necessary (AI scoping) | HIPAA §164.502(b) | Implemented (capability enforcement) |
| Integrity of AI-processed PHI | HIPAA §164.312(c)(1) | Implemented (message signing) |
| Supervision of automated tools | HITRUST 01.c, NIST 800-66 | Implemented (HITL gates, trust levels) |

---

## X. Multi-Tenancy & Data Isolation

### What Evaluators Look For

- Is PHI isolated between covered entities and business associates?
- Can tenant-level access controls enforce HIPAA segmentation?
- Is per-tenant data independently manageable (export, deletion, hold)?
- Does multi-tenancy support varying compliance configurations?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Tenant-Scoped Redis Keys** | `tenant_scoped_key()` utility generates `tenant:{id}:{key}` prefixed keys - all data operations scoped to tenant context. PHI from one covered entity cannot be accessed from another tenant's context. No cross-tenant queries permitted at the data layer | `core/tenancy.py` |
| **Client/Matter Association** | Data organized within tenants by client matter - supports patient, episode, referral, and case types with lifecycle management (active > closed > hold). Each matter scopes PHI to a specific patient or care context | `core/tenancy.py` |
| **Litigation Hold Support Per Tenant** | Individual matters or entire tenants can be placed on legal hold, preventing PHI deletion during HHS investigations, malpractice litigation, or compliance audits. Hold overrides retention-based deletion | `core/tenancy.py`, `core/legal_hold.py` |
| **Four-Tier Data Classification** | PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED. Per-tenant classification defaults configurable - healthcare tenants default to CONFIDENTIAL, PHI fields auto-classified as RESTRICTED. Classification drives encryption, access control, audit, and retention requirements | `core/data_classification.py` |
| **Tenant Type Classification** | Tenant types include law_firm, insurance, real_estate, healthcare, small_business, personal, general - each with pre-configured compliance defaults and data handling policies | `core/tenancy.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| PHI isolation between entities | HIPAA §164.312(a)(1), §164.314(a) | Implemented |
| Business associate data segmentation | HIPAA §164.308(b)(1) | Implemented |
| Minimum necessary per entity | HIPAA §164.502(b) | Implemented (tenant scoping) |
| Data preservation for investigations | HIPAA §164.530(j) | Implemented (legal hold) |
| Entity-specific security configurations | HIPAA §164.308(a)(1) | Implemented (per-tenant overrides) |

---

## XI. Incident Response

### What Evaluators Look For

- How are breaches assessed for severity and PHI exposure?
- Are notification deadlines tracked against HIPAA/HITECH timelines?
- Is there a regulatory notification workflow (HHS, state AG, individuals)?
- Can threat response be automated for critical incidents?
- Is the breach risk assessment documented per the four-factor test?

### ClawCoat Implementation

| Control | Implementation | Files |
|---------|---------------|-------|
| **Breach Severity Assessment** | Four-level severity classification (Critical/High/Medium/Low) with PHI-specific factors: number of individuals affected, types of PHI exposed (demographic, clinical, financial, genomic), likelihood of re-identification, whether data was encrypted (safe harbor), containment status progression | `core/breach_notification.py` |
| **HIPAA Four-Factor Risk Assessment** | Automated assessment of: (1) nature and extent of PHI involved, (2) unauthorized person who used/accessed PHI, (3) whether PHI was actually acquired or viewed, (4) extent of risk mitigation. Determines whether breach notification is required or if low-probability exception applies | `core/breach_notification.py` |
| **Notification Deadline Tracking** | HIPAA-specific deadlines enforced: individuals within 60 days of discovery, HHS within 60 days (if >500 affected) or annual log (if <500), state attorney general within 60 days (if >500 in state), media notification (if >500 in jurisdiction). `get_overdue_notifications()` identifies past-deadline items | `core/breach_notification.py` |
| **Regulatory Notification Workflow** | Per-recipient notification records (HHS_OCR, state_attorney_general, affected_individual, media, law_enforcement) with method, send status, acknowledgment tracking, and content documentation. Workflow supports staged notification with legal review gates | `core/breach_notification.py` |
| **Threat Response Automation** | Critical threats trigger automatic agent quarantine, API key revocation, rate limiting escalation, PHI access lockdown. Graduated response: isolate > contain > investigate > remediate > restore. All automated actions audit-logged | `core/threat_response.py` |
| **Incident Documentation** | Full incident lifecycle documentation: detection, assessment, containment, notification, remediation, post-incident review. Exportable incident reports for HHS investigation response | `core/breach_notification.py` |

### Regulatory Mapping

| Requirement | Regulation | Status |
|-------------|-----------|--------|
| Risk assessment of breach | HIPAA §164.402 | Implemented (four-factor test) |
| Notification to individuals | HIPAA §164.404, HITECH §13402(a) | Implemented |
| Notification to HHS | HIPAA §164.408, HITECH §13402(b) | Implemented |
| Notification to media | HIPAA §164.406 | Implemented (>500 threshold) |
| Notification timeline (60 days) | HIPAA §164.404(b), HITECH §13402(d) | Implemented |
| Breach log (under 500) | HIPAA §164.408(c) | Implemented |
| Encryption safe harbor | HITECH §13402(h) | Implemented (AES-256-GCM) |

---

## XII. Quick Reference: HIPAA Security Rule Mapping

### §164.308 - Administrative Safeguards

| HIPAA Section | Requirement | TelsonBase Module | Status |
|---------------|-------------|-------------------|--------|
| §164.308(a)(1)(i) | Security management process | `core/compliance.py`, `core/hitrust_controls.py` | Implemented |
| §164.308(a)(1)(ii)(A) | Risk analysis | `core/hitrust_controls.py` | Implemented |
| §164.308(a)(1)(ii)(B) | Risk management | `core/hitrust_controls.py` | Implemented |
| §164.308(a)(1)(ii)(C) | Sanction policy | `core/sanctions.py` | Implemented |
| §164.308(a)(1)(ii)(D) | Information system activity review | `core/audit.py` | Implemented |
| §164.308(a)(3) | Workforce security | `core/rbac.py`, `core/sanctions.py` | Implemented |
| §164.308(a)(4) | Information access management | `core/rbac.py`, `core/minimum_necessary.py` | Implemented |
| §164.308(a)(5) | Security awareness and training | `core/training.py` | Implemented |
| §164.308(a)(6) | Security incident procedures | `core/breach_notification.py`, `core/threat_response.py` | Implemented |
| §164.308(a)(7) | Contingency plan | `core/contingency_testing.py` | Implemented |
| §164.308(a)(7)(ii)(D) | Testing and revision procedures | `core/contingency_testing.py` | Implemented |
| §164.308(b) | Business associate contracts | `core/baa_tracking.py` | Implemented |

### §164.310 - Physical Safeguards

| HIPAA Section | Requirement | TelsonBase Module | Status |
|---------------|-------------|-------------------|--------|
| §164.310(a)(1) | Facility access controls | `docker-compose.yml` (network isolation) | Implemented (logical) |
| §164.310(b) | Workstation use | `core/session_management.py` | Implemented |
| §164.310(c) | Workstation security | `core/session_management.py`, `core/mfa.py` | Implemented |
| §164.310(d)(1) | Device and media controls | `core/secure_storage.py`, `core/data_retention.py` | Implemented |

### §164.312 - Technical Safeguards

| HIPAA Section | Requirement | TelsonBase Module | Status |
|---------------|-------------|-------------------|--------|
| §164.312(a)(1) | Access control | `core/rbac.py`, `core/capabilities.py` | Implemented |
| §164.312(a)(2)(i) | Unique user identification | `core/audit.py` (ActorType) | Implemented |
| §164.312(a)(2)(ii) | Emergency access procedure | `core/emergency_access.py` | Implemented |
| §164.312(a)(2)(iii) | Automatic logoff | `core/session_management.py` | Implemented |
| §164.312(a)(2)(iv) | Encryption and decryption | `core/secure_storage.py` | Implemented |
| §164.312(b) | Audit controls | `core/audit.py` | Implemented |
| §164.312(c)(1) | Integrity | `core/secure_storage.py` (HMAC-SHA256) | Implemented |
| §164.312(c)(2) | Mechanism to authenticate ePHI | `core/secure_storage.py` (GCM tags) | Implemented |
| §164.312(d) | Person or entity authentication | `core/auth.py`, `core/mfa.py` | Implemented |
| §164.312(e)(1) | Transmission security | `docker-compose.yml` (Traefik TLS) | Implemented |
| §164.312(e)(2)(i) | Integrity controls (transmission) | `core/signing.py` (HMAC-SHA256) | Implemented |
| §164.312(e)(2)(ii) | Encryption (transmission) | `docker-compose.yml` (TLS 1.2+) | Implemented |

### §164.314 - Organizational Requirements

| HIPAA Section | Requirement | TelsonBase Module | Status |
|---------------|-------------|-------------------|--------|
| §164.314(a)(1) | Business associate contracts | `core/baa_tracking.py` | Implemented |
| §164.314(a)(2) | BA contract requirements | `core/baa_tracking.py` | Implemented |
| §164.314(b) | Group health plan requirements | N/A (configurable per tenant) | Addressable |

### §164.316 - Policies, Procedures, and Documentation

| HIPAA Section | Requirement | TelsonBase Module | Status |
|---------------|-------------|-------------------|--------|
| §164.316(a) | Policies and procedures | `docs/`, `core/compliance.py` | Implemented |
| §164.316(b)(1) | Documentation | `core/audit.py`, `core/compliance.py` | Implemented |
| §164.316(b)(2)(i) | Time limit (6-year retention) | `core/data_retention.py` | Implemented |
| §164.316(b)(2)(ii) | Availability | `core/compliance.py` (export) | Implemented |
| §164.316(b)(2)(iii) | Updates | `core/compliance.py` (versioned) | Implemented |

---

## XIII. Quick Reference: HITECH Act Compliance

### Breach Notification Requirements

| HITECH Requirement | Implementation | Status |
|--------------------|---------------|--------|
| Individual notification within 60 days | `core/breach_notification.py` - deadline tracking with overdue detection | Implemented |
| HHS notification (>500 individuals) | `core/breach_notification.py` - immediate notification workflow | Implemented |
| HHS annual log (<500 individuals) | `core/breach_notification.py` - annual breach log compilation | Implemented |
| Media notification (>500 in jurisdiction) | `core/breach_notification.py` - media notification trigger | Implemented |
| Content requirements for notification | `core/breach_notification.py` - structured notification templates | Implemented |
| Encryption safe harbor | `core/secure_storage.py` - AES-256-GCM (NIST-approved, renders PHI "secured") | Implemented |

### Meaningful Use Security Requirements

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| Protect electronic health information | AES-256-GCM encryption, RBAC, MFA, audit trail | Implemented |
| Risk analysis conducted | `core/hitrust_controls.py` - risk assessment tracking | Implemented |
| Access control implemented | `core/rbac.py`, `core/capabilities.py`, `core/trust_levels.py` | Implemented |
| Audit log enabled | `core/audit.py` - SHA-256 hash-chained, 47 event types | Implemented |

### Business Associate Obligations

| Obligation | Implementation | Status |
|------------|---------------|--------|
| Safeguards for PHI | Full technical safeguard stack (encryption, access control, audit) | Implemented |
| Report breaches to covered entity | `core/breach_notification.py` - multi-recipient notification workflow | Implemented |
| BAA execution and tracking | `core/baa_tracking.py` - lifecycle management with annual review | Implemented |
| Return or destroy PHI on termination | `core/data_retention.py` - tenant-scoped deletion with audit trail | Implemented |
| Ensure subcontractor compliance | `core/baa_tracking.py` - downstream BA tracking | Implemented |

---

## XIV. Architecture Diagram - HIPAA Security Layers

```
                    INTERNET
                       |
              [Traefik - TLS 1.2+]      Port 80/443 only
              [HTTPS Redirect]           [Let's Encrypt ACME]
                       |
            +----- FRONTEND NETWORK -----+
            |          |                 |
      [MCP/mcp]   [Open-WebUI]    [MCP Server]     <-- localhost-bound except MCP
            |                         |    |
            |              +--- BACKEND NETWORK ---+
            |              |          |            |
            |          [Worker]    [Beat]    [TelsonBase Core]
            |              |          |            |
            |              |   +------+------+     |
            |              |   |  HIPAA Controls   |
            |              |   |  +-----------+    |
            |              |   |  | PHI Disc.  |   |  core/phi_disclosure.py
            |              |   |  | Min. Nec.  |   |  core/minimum_necessary.py
            |              |   |  | De-Ident.  |   |  core/phi_deidentification.py
            |              |   |  | Emergency  |   |  core/emergency_access.py
            |              |   |  | BAA Track  |   |  core/baa_tracking.py
            |              |   |  | Sanctions  |   |  core/sanctions.py
            |              |   |  | Training   |   |  core/training.py
            |              |   |  | HITRUST    |   |  core/hitrust_controls.py
            |              |   |  +-----------+    |
            |              |   +------+------+     |
            |              |          |            |
            |    +---- DATA NETWORK (internal) ----+
            |    |         |                       |
            | [Redis]  [Mosquitto]                 |
            |  (auth)    (auth)                    |
            |  (PHI encrypted at rest)             |
            |  (AOF persistence)                   |
            |                                      |
            +------ AI NETWORK (internal) ---------+
            |              |                       |
         [Ollama]    [MCP Server]            [MONITORING]
        (local LLM)  (bridges all)        [Prometheus/Grafana]
        (no PHI sent  (capability          (internal only)
         externally)   enforced)
```

### Data Flow - PHI Access Request

```
  User Request
       |
  [Authentication] ──> core/auth.py, core/mfa.py
       |
  [Session Check] ──> core/session_management.py (auto-logoff)
       |
  [RBAC Check] ──> core/rbac.py (role has PHI permission?)
       |
  [Minimum Necessary] ──> core/minimum_necessary.py (scope to needed fields)
       |
  [Capability Check] ──> core/capabilities.py (agent has PHI capability?)
       |
  [Audit Log] ──> core/audit.py (SHA-256 chain, ActorType recorded)
       |
  [Decrypt PHI] ──> core/secure_storage.py (AES-256-GCM + HMAC verify)
       |
  [Disclosure Tracking] ──> core/phi_disclosure.py (if external disclosure)
       |
  Response (minimum necessary fields only)
```

---

## XV. Security Contact & Vulnerability Reporting

- **Security Policy:** `SECURITY.md` in project root
- **Vulnerability Reporting:** Responsible disclosure process documented
- **Response Times:** Critical (24h), High (7d), Medium (30d), Low (next release)
- **Contact:** support@clawcoat.com

---

*This document is intended for healthcare compliance evaluators, HIPAA security auditors, HITRUST assessors, and enterprise procurement teams assessing TelsonBase for deployment in healthcare-adjacent or healthcare-ready environments. TelsonBase does not currently process PHI in production - this document demonstrates infrastructure readiness for HIPAA/HITECH/HITRUST compliance. For current production compliance details covering real estate and legal markets, see `LEGAL_COMPLIANCE.md`. For technical implementation details, refer to the referenced source files.*

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
