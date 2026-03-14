# ClawCoat - Compliance Certification Roadmap

**Version:** v11.0.1 · **Updated:** March 8, 2026 · **Maintainer:** Quietfire AI
**Platform:** Zero-Trust AI Agent Security Platform
**Target Markets:** Law Firms · Insurance · Healthcare · Real Estate · Accounting

---

## I. Executive Summary

This document defines the certification and compliance roadmap for TelsonBase, a self-hosted zero-trust AI agent orchestration platform. TelsonBase currently serves law firms (primary revenue market, $150-1000/seat/month) and real estate brokerages (entry market, low compliance bar), with forward-looking healthcare-adjacent compliance infrastructure already built into the platform.

The self-hosted deployment model is TelsonBase's principal compliance advantage. All data remains on the customer's premises. No client data is transmitted to third-party AI services. Local AI inference via Ollama means attorney-client privilege is preserved by architecture, not by policy. This fundamentally simplifies every certification path described below -- the data residency question that consumes weeks of audit effort in cloud-hosted platforms is answered at the architecture level.

This roadmap covers six certification targets across a phased 12-18 month timeline, with a total estimated budget of $50-125K. Each phase builds on existing controls documented in `LEGAL_COMPLIANCE.md`, `HEALTHCARE_COMPLIANCE.md`, and `ENCRYPTION_AT_REST.md`.

---

## II. Current Compliance Posture Summary

### HIPAA/HITECH Infrastructure

TelsonBase maintains 12 compliance modules implemented and operational in the codebase:

| Module | File | Purpose |
|--------|------|---------|
| Legal Hold | `core/legal_hold.py` | ESI preservation, deletion override, custodian tracking |
| Breach Notification | `core/breach_notification.py` | Severity classification, notification deadlines, HHS/individual/media workflow |
| Data Retention | `core/data_retention.py` | Per-tenant retention policies, CCPA deletion workflow, 6-year HIPAA minimum |
| Sanctions | `core/sanctions.py` | Workforce violation tracking, severity levels, appeal process |
| Training | `core/training.py` | Security awareness program, module tracking, annual recertification |
| Contingency Testing | `core/contingency_testing.py` | DR plan testing (tabletop, simulation, full failover), findings tracking |
| BAA Tracking | `core/baa_tracking.py` | Business Associate Agreement lifecycle, amendment history, annual review |
| HITRUST Controls | `core/hitrust_controls.py` | 75+ controls tracked across 12 CSF domains, risk assessment scoring |
| PHI Disclosure | `core/phi_disclosure.py` | Disclosure accounting, 6-year history, HHS inquiry export |
| PHI De-identification | `core/phi_deidentification.py` | Safe Harbor method, 18 HIPAA identifiers removed |
| Minimum Necessary | `core/minimum_necessary.py` | Policy engine for minimum necessary access, bulk access flagging |
| Compliance | `core/compliance.py` | SOC 2 control mapping, evidence collection, report generation |

### SOC 2 Controls

SOC 2 Trust Service Criteria controls are documented and mapped:

- 10 controls defined (CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC7.1, CC7.2, CC7.3, CC7.4, CC8.1)
- Evidence collection framework with registered evidence collectors per control
- Cryptographic audit chain (SHA-256 hash-linked, tamper-evident)
- RBAC with 5 roles and 24 granular permissions across 140+ endpoints
- MFA (TOTP RFC 6238) with role-based enforcement
- Session management with configurable auto-logoff

### Self-Hosted Compliance Advantage

The self-hosted model eliminates or simplifies several certification concerns:

| Concern | Cloud-Hosted Complexity | TelsonBase (Self-Hosted) |
|---------|------------------------|--------------------------|
| Data residency | Multi-region, cross-border, DPA required | Data never leaves customer premises |
| Third-party AI training | Contractual prohibitions, vendor due diligence | Local Ollama inference, no external API calls |
| Attorney-client privilege | Risk of waiver via third-party access | Preserved by architecture |
| Vendor risk assessment | Extensive cloud provider evaluation | Customer controls their own infrastructure |
| Encryption key custody | Cloud provider manages keys (or BYOK complexity) | Customer owns all keys |
| Subprocessor chain | Cloud vendor subprocessors require tracking | No subprocessors -- single deployment |

---

## III. HITRUST CSF Certification Path

### Current State

TelsonBase maintains a HITRUST controls module (`core/hitrust_controls.py`) with pre-mapped controls across all 12 HITRUST CSF domains:

| Domain | Description | Controls Mapped |
|--------|-------------|----------------|
| 01 | Information Protection Program | Data classification, retention, legal hold, PHI handling |
| 02 | Endpoint Protection | Session management, auto-logoff, security headers |
| 03 | Portable Media Security | AES-256-GCM encryption at rest, data classification |
| 04 | Mobile Device Security | Token-based auth, session timeout, MFA enforcement |
| 05 | Wireless Security | Network segmentation, internal-only Docker networks |
| 06 | Configuration Management | Docker Compose declarative config, production secret validation |
| 07 | Vulnerability Management | Egress firewall, rate limiting, anomaly detection |
| 08 | Network Protection | Five Docker networks, internal enforcement, CORS, security headers |
| 09 | Transmission Protection | TLS 1.2+, HMAC-SHA256 message signing, mTLS federation |
| 10 | Password Management | PBKDF2 key derivation, SHA-256 hashed API keys, TOTP MFA |
| 11 | Access Control | RBAC, capability sandboxing, trust levels, emergency access |
| 12 | Audit Logging and Monitoring | SHA-256 hash-chained audit, 47 event types, chain verification |

Risk assessment tracking is built in: per-control inherent risk, residual risk, control effectiveness scoring (0-100), risk owner assignment, review date tracking, and remediation plan linkage.

### Certification Timeline: HITRUST CSF e1 Assessment

The HITRUST e1 assessment is the entry-level validated assessment, covering approximately 44 controls. It is designed for organizations demonstrating foundational cybersecurity hygiene.

| Phase | Activity | Duration | Cost Estimate |
|-------|----------|----------|---------------|
| 1 | Self-assessment using MyCSF portal | 4-6 weeks | $0 (internal labor) |
| 2 | Gap remediation based on self-assessment findings | 4-8 weeks | $5-10K (remediation effort) |
| 3 | Readiness assessment with approved assessor | 2-4 weeks | $5-10K (assessor fees) |
| 4 | Validated assessment (e1) | 4-6 weeks | $10-20K (assessor fees) |
| **Total** | | **6-12 months** | **$15-30K** |

### Steps to Certification

1. **Register with HITRUST Alliance** and obtain access to MyCSF (HITRUST's assessment platform).
2. **Conduct self-assessment** by populating MyCSF with TelsonBase's existing control mappings from `core/hitrust_controls.py`. The 75+ pre-mapped controls provide a significant head start.
3. **Engage a HITRUST Authorized External Assessor** for readiness assessment. The assessor will identify gaps between TelsonBase's current controls and e1 requirements.
4. **Remediate identified gaps.** Based on current control coverage, expected gaps are primarily procedural (documented policies, formal risk assessment process) rather than technical.
5. **Complete validated assessment.** The assessor evaluates control implementation and submits results to HITRUST for quality review and certification.

### Strategic Benefit

HITRUST CSF certification is accepted by healthcare organizations as evidence of security maturity. A single HITRUST certification replaces the need for multiple point-in-time assessments from individual healthcare clients. For TelsonBase's law firm customers who handle healthcare-adjacent work (medical malpractice, health law, insurance defense), HITRUST certification provides a competitive differentiator.

---

## IV. HIPAA Compliance

### Business Associate Agreement (BAA) Readiness

TelsonBase provides BAA lifecycle management via `core/baa_tracking.py`:

- BAA status tracking: draft, active, terminated, expired
- Counterparty details and effective/expiration date management
- Amendment history with full audit trail
- Required security provisions verification checklist
- Annual review enforcement with overdue detection
- BAA template available for customer use

Under the HIPAA shared responsibility model, TelsonBase acts as a Business Associate when deployed for covered entities or their law firms. The BAA tracking module ensures all downstream BA relationships are documented and reviewed annually.

### Administrative Safeguards (HIPAA 164.308)

| Safeguard | HIPAA Section | TelsonBase Module | Status |
|-----------|---------------|-------------------|--------|
| Security management process | 164.308(a)(1)(i) | `core/compliance.py`, `core/hitrust_controls.py` | Implemented |
| Risk analysis | 164.308(a)(1)(ii)(A) | `core/hitrust_controls.py` | Implemented (tooling) |
| Risk management | 164.308(a)(1)(ii)(B) | `core/hitrust_controls.py` | Implemented (tooling) |
| Sanction policy | 164.308(a)(1)(ii)(C) | `core/sanctions.py` | Implemented |
| Information system activity review | 164.308(a)(1)(ii)(D) | `core/audit.py` | Implemented |
| Workforce security | 164.308(a)(3) | `core/rbac.py`, `core/sanctions.py` | Implemented |
| Information access management | 164.308(a)(4) | `core/rbac.py`, `core/minimum_necessary.py` | Implemented |
| Security awareness and training | 164.308(a)(5) | `core/training.py` | Implemented |
| Security incident procedures | 164.308(a)(6) | `core/breach_notification.py` | Implemented |
| Contingency plan | 164.308(a)(7) | `core/contingency_testing.py` | Implemented |
| Business associate contracts | 164.308(b) | `core/baa_tracking.py` | Implemented |

### Physical Safeguards (HIPAA 164.310)

Physical safeguards fall under the customer's responsibility in TelsonBase's shared responsibility model. TelsonBase provides logical equivalents:

| Safeguard | HIPAA Section | Responsibility | TelsonBase Contribution |
|-----------|---------------|----------------|------------------------|
| Facility access controls | 164.310(a)(1) | Customer | Docker network isolation (5 networks, 3 internal-only) |
| Workstation use | 164.310(b) | Customer | Session management with auto-logoff policies |
| Workstation security | 164.310(c) | Customer | MFA enforcement, session timeout, security headers |
| Device and media controls | 164.310(d)(1) | Customer | Application-level encryption, data retention policies |

Customers must provide: locked server rooms, physical access controls to deployment hardware, visitor logs, hardware inventory, and media disposal procedures.

### Technical Safeguards (HIPAA 164.312)

| Safeguard | HIPAA Section | TelsonBase Module | Status |
|-----------|---------------|-------------------|--------|
| Access control | 164.312(a)(1) | `core/rbac.py`, `core/capabilities.py` | Implemented |
| Unique user identification | 164.312(a)(2)(i) | `core/audit.py` (ActorType enumeration) | Implemented |
| Emergency access procedure | 164.312(a)(2)(ii) | `core/emergency_access.py` | Implemented |
| Automatic logoff | 164.312(a)(2)(iii) | `core/session_management.py` | Implemented |
| Encryption and decryption | 164.312(a)(2)(iv) | `core/secure_storage.py` (AES-256-GCM) | Implemented |
| Audit controls | 164.312(b) | `core/audit.py` (SHA-256 hash-chained) | Implemented |
| Integrity | 164.312(c)(1) | `core/secure_storage.py` (HMAC-SHA256) | Implemented |
| Authentication of ePHI | 164.312(c)(2) | `core/secure_storage.py` (GCM auth tags) | Implemented |
| Person/entity authentication | 164.312(d) | `core/auth.py`, `core/mfa.py` | Implemented |
| Transmission security | 164.312(e)(1) | Traefik TLS 1.2+ | Implemented |

### Gap: Formal HIPAA Security Risk Assessment (SRA)

While TelsonBase provides the tooling for risk analysis (`core/hitrust_controls.py` with per-control risk scoring), a formal HIPAA Security Risk Assessment has not been conducted by an independent assessor. The SRA is required under HIPAA 164.308(a)(1)(ii)(A) and is a prerequisite for demonstrating compliance to covered entity clients.

**Remediation plan:**
1. Engage a qualified HIPAA security assessor (OCR-recognized methodology preferred)
2. Conduct full SRA covering all 164.308, 164.310, and 164.312 requirements
3. Document risk register with inherent risk, controls, residual risk, and remediation plans
4. Integrate findings into `core/hitrust_controls.py` risk assessment tracking
5. Establish annual SRA review cadence

**Estimated cost:** $5-15K depending on assessor and scope
**Estimated timeline:** 1-2 months

---

## V. SOC 2 Type II Path

### Current State: Type I Documentation

TelsonBase has completed SOC 2 Type I documentation (self-assessed), mapping controls to AICPA Trust Service Criteria:

| Control ID | Trust Service Criteria | TelsonBase Implementation | Evidence |
|------------|----------------------|---------------------------|----------|
| CC6.1 | Logical access controls | RBAC (5 roles, 24 permissions), MFA (TOTP RFC 6238) | `core/rbac.py`, `core/mfa.py` |
| CC6.2 | User registration and authorization | User management with registration, profile, deactivation | `core/user_management.py` |
| CC6.3 | Access removal on termination | Session invalidation on deactivation, API key revocation | `core/rbac.py`, `core/auth.py` |
| CC6.6 | Network segmentation | 5 Docker networks, 3 internal-only, egress firewall | `docker-compose.yml` |
| CC6.7 | Data protection | AES-256-GCM at rest, TLS 1.2+ in transit, data classification | `core/secure_storage.py` |
| CC7.1 | Threat detection | Rate limiting, anomaly detection, behavioral monitoring | `core/middleware.py`, `core/anomaly.py` |
| CC7.2 | Security event monitoring | SHA-256 hash-chained audit, 47 event types, chain verification | `core/audit.py` |
| CC7.3 | Incident response | Breach assessment, notification workflow, 4-severity classification | `core/breach_notification.py` |
| CC7.4 | Business continuity | Backup/restore (RPO 24h, RTO 15min), contingency plan testing | `scripts/backup.sh`, `core/contingency_testing.py` |
| CC8.1 | Change management | Cryptographic audit chain records all configuration changes | `core/audit.py` |

### Path to SOC 2 Type II

SOC 2 Type II differs from Type I in that it evaluates the operating effectiveness of controls over an observation period, not just their design.

| Phase | Activity | Duration | Cost Estimate |
|-------|----------|----------|---------------|
| 1 | Select CPA firm with SOC 2 experience | 2-4 weeks | $0 (selection process) |
| 2 | Type I report (formal, auditor-issued) | 4-6 weeks | $15-25K (if formal report desired) |
| 3 | Remediate any Type I findings | 2-4 weeks | $0-5K (internal effort) |
| 4 | Observation period (controls operating) | 6-12 months | $0 (ongoing operations) |
| 5 | Type II audit and report issuance | 4-6 weeks | $20-50K (auditor fees) |
| **Total** | | **12-18 months** | **$20-50K** |

### Steps to Type II

1. **Engage a CPA firm** registered with the AICPA for SOC 2 engagements. Select a firm with experience in technology platforms and legal/healthcare verticals.
2. **Formalize Type I report.** The current self-assessed documentation provides the foundation. An auditor will evaluate control design and issue a formal Type I report.
3. **Remediate gaps** identified during the Type I audit. Expected gaps are primarily procedural: documented change management policy, formal access review cadence, vendor management policy.
4. **Begin observation period.** Controls must be demonstrated as operating effectively over a minimum 6-month period. During this time, maintain all audit logs, access reviews, incident response records, and change management documentation.
5. **Complete Type II audit.** The auditor tests controls at multiple points during the observation period, reviews evidence, and issues the Type II report.

### Strategic Benefit

SOC 2 Type II is the standard vendor security certification required by enterprise law firms and their clients. Without a SOC 2 Type II report, TelsonBase will face objections during procurement by Am Law 200 firms and corporate legal departments. This certification directly enables the $150-1000/seat/month revenue tier.

---

## VI. SOX Mapping

### Applicability

TelsonBase is not itself subject to the Sarbanes-Oxley Act (SOX). SOX applies to publicly traded companies and their financial reporting. However, TelsonBase may be deployed by law firms that serve publicly traded clients subject to SOX, or by corporate legal departments within SOX-regulated companies. In these scenarios, TelsonBase functions as a tool supporting the client's SOX compliance obligations.

### Relevant Control Mapping

| SOX Requirement | PCAOB/COSO Reference | TelsonBase Control | Implementation |
|-----------------|---------------------|-------------------|----------------|
| Change management controls | COSO Principle 11 | Cryptographic audit chain | `core/audit.py` -- SHA-256 hash-linked entries, tamper-evident, all configuration changes recorded |
| Access controls | COSO Principle 12 | RBAC + MFA | `core/rbac.py`, `core/mfa.py` -- 5 roles, 24 permissions, TOTP MFA with role-based enforcement |
| Segregation of duties | COSO Principle 10 | Role-based permission model | `core/rbac.py` -- distinct Viewer, Operator, Admin, Security Officer, Super Admin roles |
| Data integrity | COSO Principle 13 | HMAC-SHA256 integrity verification | `core/secure_storage.py` -- integrity tags on stored data, verified on every read |
| Audit trail | COSO Principle 16 | Tamper-evident logging | `core/audit.py` -- 47 event types, monotonic sequencing, chain verification endpoint |
| Logical access to financial data | COSO Principle 12 | Tenant-scoped data isolation | `core/tenancy.py` -- client-matter isolation, Redis key namespacing |
| IT general controls (ITGC) | PCAOB AS 2201 | Session management, encryption | `core/session_management.py`, `core/secure_storage.py` |
| Monitoring of controls | COSO Principle 16 | Prometheus alerting, Grafana dashboards | Prometheus alert rules (HighErrorRate, AuthFailureSpike, AuditChainBroken) |

### Positioning Statement

TelsonBase provides the technical controls that enable SOX-regulated organizations to meet their IT General Control (ITGC) requirements when using TelsonBase for legal workflow management. The cryptographic audit chain, role-based access controls, and data integrity mechanisms provide auditable evidence for SOX Section 404 internal control assessments. TelsonBase does not generate, process, or store financial statements and is therefore not in scope for SOX audits as a service organization.

---

## VII. CJIS Security Policy

### Applicability

The Criminal Justice Information Services (CJIS) Security Policy applies when law firm personnel access Criminal Justice Information (CJI) in the course of criminal defense representation, public defender work, or law enforcement advisory engagements. If TelsonBase stores or processes documents containing CJI (arrest records, rap sheets, court documents with CJIS-sourced data), the CJIS Security Policy requirements apply.

### Controls Mapping

| CJIS Requirement | Policy Section | TelsonBase Control | Status |
|------------------|---------------|-------------------|--------|
| Encryption at rest | 5.10.1.2 | AES-256-GCM (application), volume encryption (customer) | Implemented |
| Encryption in transit | 5.10.1.1 | TLS 1.2+ via Traefik | Implemented |
| Multi-factor authentication | 5.6.2.2 | TOTP MFA (RFC 6238) with role-based enforcement | Implemented |
| Advanced authentication | 5.6.2.2.1 | MFA required for all remote access to CJI | Implemented |
| Audit logging | 5.4.1 | SHA-256 hash-chained audit, 47 event types | Implemented |
| Session management | 5.5.5 | Configurable timeout, auto-logoff, session invalidation | Implemented |
| Access control | 5.5 | RBAC (5 roles, 24 permissions), capability sandboxing | Implemented |
| Personnel security | 5.12 | Sanctions tracking, training module | Implemented |
| Media protection | 5.8 | Application-level encryption, data classification | Implemented |
| Physical protection | 5.9 | Customer responsibility (shared model) | Customer scope |
| Network security | 5.10.1 | 5 Docker networks, 3 internal-only, egress firewall | Implemented |
| Incident response | 5.3 | Breach notification, threat response automation | Implemented |

### Gap: FIPS 140-2 Validated Encryption

**This is the most significant CJIS compliance gap.**

CJIS Security Policy Section 5.10.1.2 requires FIPS 140-2 validated cryptographic modules for encryption of CJI at rest and in transit. TelsonBase currently uses:

- **Fernet** (AES-128-CBC + HMAC-SHA256) via the `cryptography` Python library for MFA secret storage
- **AES-256-GCM** via the `cryptography` Python library for sensitive field encryption
- **TLS 1.2+** via Traefik/OpenSSL for transport encryption

The `cryptography` Python library uses OpenSSL as its backend. OpenSSL has FIPS-validated builds, but the standard PyPI distribution of `cryptography` does not use a FIPS-validated OpenSSL module. The Fernet implementation specifically uses AES-128-CBC, which is a FIPS-approved algorithm but is not being executed within a FIPS-validated boundary.

**Remediation plan:**
1. Replace standard OpenSSL with a FIPS 140-2 validated OpenSSL module in the Docker build (e.g., OpenSSL 3.0 FIPS provider)
2. Configure the `cryptography` library to use the FIPS provider
3. Evaluate replacing Fernet (AES-128-CBC) with AES-256-GCM for MFA secret storage to use a single, stronger algorithm
4. Validate Traefik TLS configuration uses FIPS-approved cipher suites only
5. Document FIPS validation evidence (module certificate numbers, configuration attestation)

**Estimated cost:** $10-20K (engineering effort for FIPS-validated Docker build, cipher suite configuration, testing)
**Estimated timeline:** 3-6 months

---

## VIII. GDPR Considerations

### Applicability

The General Data Protection Regulation (GDPR) applies when TelsonBase is deployed by law firms or real estate brokerages that process personal data of individuals located in the European Union, regardless of where the processing occurs. This includes U.S. law firms with EU clients, international transaction work, or cross-border litigation.

### Data Processing Agreement (DPA)

TelsonBase's self-hosted architecture simplifies GDPR compliance. A Data Processing Agreement template is available covering:

- Scope and purpose of processing
- Categories of personal data and data subjects
- Processor obligations (security measures, sub-processor restrictions, breach notification)
- Data transfer mechanisms (not applicable for self-hosted -- data remains on customer premises)
- Data subject rights facilitation
- Audit rights

Because TelsonBase is self-hosted, there is no cross-border data transfer. The customer acts as the Data Controller, and TelsonBase (as software) does not independently process data. This eliminates the need for Standard Contractual Clauses (SCCs), Binding Corporate Rules (BCRs), or adequacy decisions.

### Data Subject Rights Implementation

| GDPR Right | Article | TelsonBase Implementation | Status |
|------------|---------|---------------------------|--------|
| Right of access | Art. 15 | API endpoints for data export per tenant/matter | Implemented |
| Right to rectification | Art. 16 | Data management API endpoints, audit trail of changes | Implemented |
| Right to erasure | Art. 17 | `core/data_retention.py` -- deletion workflow with approval gate, legal hold check | Implemented |
| Right to restriction | Art. 18 | Matter lifecycle management (active/closed/hold states) | Implemented |
| Right to data portability | Art. 20 | Compliance export (`export_chain_for_compliance()`), JSON format | Implemented |
| Right to object | Art. 21 | Configurable per-tenant processing policies | Implemented |
| Automated decision-making | Art. 22 | HITL approval gates on all AI-driven decisions | Implemented |

### GDPR-Specific Controls

| GDPR Principle | Article | TelsonBase Control |
|---------------|---------|-------------------|
| Data minimization | Art. 5(1)(c) | `core/minimum_necessary.py` -- policy engine restricting access to needed fields only |
| Breach notification (72 hours) | Art. 33 | `core/breach_notification.py` -- severity assessment within 72-hour window, overdue detection |
| Data protection by design | Art. 25 | Zero-trust architecture, capability-based sandboxing, encryption by default |
| Data protection by default | Art. 25 | RESTRICTED classification for sensitive data, MFA enforcement, minimum necessary access |
| Records of processing | Art. 30 | SHA-256 hash-chained audit log, 47 event types, per-tenant processing records |
| Data protection impact assessment | Art. 35 | `core/hitrust_controls.py` -- risk assessment framework (adaptable for DPIA) |
| International transfers | Art. 44-49 | Not applicable -- self-hosted, data never leaves customer premises |

### Remediation for Full GDPR Readiness

1. **Formalize DPA template** with legal counsel review for EU jurisdictional requirements
2. **Implement consent management** tracking if processing relies on consent (Art. 6(1)(a))
3. **Document lawful basis** per processing activity in records of processing
4. **Establish DPO designation guidance** for customers who require a Data Protection Officer

**Estimated cost:** $5-10K (legal counsel for DPA review and GDPR documentation)
**Estimated timeline:** 1-2 months

---

## IX. PCI DSS Considerations

### Applicability

The Payment Card Industry Data Security Standard (PCI DSS) applies only if TelsonBase directly handles, processes, stores, or transmits cardholder data (credit/debit card numbers, CVV codes, cardholder names associated with account numbers). In the standard deployment model, TelsonBase does not process payment card data -- billing and payment processing are handled externally.

### If PCI DSS Becomes Applicable

If a future TelsonBase module processes cardholder data (e.g., client billing integration, trust account management with card payments), the following controls are already aligned:

| PCI DSS Requirement | Version 4.0 Section | TelsonBase Control | Status |
|---------------------|---------------------|-------------------|--------|
| Install and maintain network security controls | 1.x | Docker network segmentation, egress firewall, Traefik reverse proxy | Aligned |
| Apply secure configurations | 2.x | Production secret validation, Docker Compose declarative config | Aligned |
| Protect stored account data | 3.x | AES-256-GCM encryption, data classification (RESTRICTED tier) | Aligned |
| Protect cardholder data in transit | 4.x | TLS 1.2+ via Traefik, HSTS headers | Aligned |
| Protect against malicious software | 5.x | Egress firewall, capability sandboxing, anomaly detection | Aligned |
| Develop secure systems and software | 6.x | CI/CD pipeline, security scanning, error sanitization | Aligned |
| Restrict access to system components | 7.x | RBAC (5 roles, 24 permissions), principle of least privilege | Aligned |
| Identify users and authenticate access | 8.x | Unique user IDs, MFA, bcrypt password hashing, session management | Aligned |
| Restrict physical access | 9.x | Customer responsibility (shared model) | Customer scope |
| Log and monitor all access | 10.x | SHA-256 hash-chained audit, 47 event types, Prometheus alerting | Aligned |
| Test security regularly | 11.x | 720 tests (96 security, 115 QMS, 129 toolroom, 55 OpenClaw, 29 E2E, 7 contract), CI/CD pipeline | Aligned |
| Support information security with policies | 12.x | Compliance documentation, training module, incident response | Aligned |

### Recommendation

PCI DSS compliance should only be pursued if TelsonBase enters a scope where cardholder data is directly processed. The current recommendation is to keep payment processing out of scope by using an external payment processor (Stripe, Square, etc.) and never storing cardholder data within TelsonBase. This is a SAQ-A approach (no cardholder data stored, processed, or transmitted) rather than SAQ-D (full assessment).

If SAQ-D scope becomes necessary, TelsonBase's existing access controls, encryption, logging, and network segmentation provide approximately 80% of required controls. The primary gap would be formal PCI vulnerability scanning (ASV scans) and penetration testing by a PCI QSA.

---

## X. Priority Roadmap

### Phase Summary

| Phase | Certification | Timeline | Cost Estimate | Priority | Rationale |
|-------|--------------|----------|---------------|----------|-----------|
| 1 | SOC 2 Type I (self-assessed) | Complete | $0 | Done | Foundation for all enterprise sales |
| 2 | HIPAA Security Risk Assessment | 1-2 months | $5-15K | High | Required for any healthcare-adjacent law firm client |
| 3 | SOC 2 Type II | 6-12 months | $20-50K | High | Required by Am Law 200 firms and enterprise procurement |
| 4 | HITRUST CSF e1 | 6-12 months | $15-30K | Medium | Healthcare market differentiator, replaces multiple assessments |
| 5 | CJIS compliance (FIPS 140-2) | 3-6 months | $10-20K | Low | Only needed for criminal defense / law enforcement clients |
| 6 | GDPR readiness | 1-2 months | $5-10K | Low | Only needed for firms with EU clients or data |

### Recommended Execution Order

**Months 1-2: Foundation (Phases 2 + 6)**

- Conduct HIPAA SRA with qualified assessor. This assessment will identify procedural gaps that also apply to SOC 2 and HITRUST, making it the highest-leverage first investment.
- Engage legal counsel for DPA/BAA template review (GDPR readiness). This is a documentation exercise with low cost and high value for international clients.

**Months 3-6: Enterprise Readiness (Phase 3 begins)**

- Engage CPA firm for formal SOC 2 Type I report.
- Remediate any findings from the HIPAA SRA and SOC 2 Type I audit.
- Begin SOC 2 Type II observation period (minimum 6 months).
- If CJIS compliance is needed, begin FIPS 140-2 validated Docker build engineering (Phase 5).

**Months 6-12: Certification Achievement (Phases 3 + 4)**

- Continue SOC 2 Type II observation period. Maintain all evidence (access reviews, incident logs, change management records).
- Begin HITRUST CSF e1 self-assessment in MyCSF portal. Leverage the HIPAA SRA and SOC 2 evidence already collected -- significant overlap reduces effort.
- Complete HITRUST readiness assessment and validated assessment.

**Months 12-18: Maturity**

- Receive SOC 2 Type II report from auditor.
- Receive HITRUST CSF e1 certification.
- Establish annual recertification cadence for both SOC 2 Type II and HITRUST.
- Evaluate upgrade path to HITRUST CSF i1 (intermediate) based on market demand.

### Gantt Overview

```
Month:    1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18
          |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
Phase 2:  [===HIPAA SRA===]
Phase 6:  [==GDPR Readiness=]
Phase 3:          [=SOC2 T1=][=======SOC 2 Type II Observation Period========][=Audit=]
Phase 4:                              [==Self-Assess==][=Readiness=][=Validated=]
Phase 5:          [=====FIPS 140-2 Engineering=====] (if needed)
```

---

## XI. Resource Requirements

### Personnel

| Role | Engagement Model | Estimated Cost | Duration |
|------|-----------------|---------------|----------|
| Compliance Officer | Part-time consultant or fractional hire | $5-15K/year | Ongoing |
| Legal Counsel | Engagement for DPA/BAA review, GDPR documentation | $5-10K | 1-2 months |
| HIPAA Security Assessor | Engagement for formal SRA | $5-15K | 1-2 months |
| SOC 2 Auditor (CPA firm) | Engagement for Type I and Type II reports | $20-50K | 12-18 months |
| HITRUST Authorized Assessor | Engagement for readiness and validated assessment | $10-20K | 4-6 months |
| Security Engineer | Internal -- FIPS 140-2 build, remediation tasks | $10-20K (if CJIS needed) | 3-6 months |

### Budget Summary

| Category | Low Estimate | High Estimate |
|----------|-------------|---------------|
| HIPAA Security Risk Assessment | $5K | $15K |
| SOC 2 Type II (auditor fees) | $20K | $50K |
| HITRUST CSF e1 (assessor + remediation) | $15K | $30K |
| GDPR readiness (legal counsel) | $5K | $10K |
| CJIS/FIPS compliance (if needed) | $10K | $20K |
| Compliance officer (12-18 months) | $5K | $15K |
| **Total** | **$50K** | **$125K** |

### Tools and Subscriptions

| Tool | Purpose | Estimated Annual Cost |
|------|---------|----------------------|
| HITRUST MyCSF portal | HITRUST self-assessment and assessment management | $2-5K/year |
| GRC platform (optional) | Centralized compliance management (Vanta, Drata, Secureframe) | $5-15K/year |
| Vulnerability scanner | Automated vulnerability scanning for SOC 2 evidence | $1-5K/year |
| Penetration testing | Annual pen test for SOC 2 and HITRUST evidence | $5-15K/year |

A GRC (Governance, Risk, and Compliance) platform is optional but recommended for organizations pursuing multiple certifications. These platforms automate evidence collection, track control status, and generate auditor-ready reports. TelsonBase's existing `core/compliance.py` and `core/hitrust_controls.py` modules provide equivalent functionality for TelsonBase-specific controls, but a GRC platform would cover organizational-level controls (HR policies, vendor management, etc.) that fall outside the software platform.

---

## XII. Cross-Framework Control Reuse

A significant cost optimization in pursuing multiple certifications is the overlap between frameworks. Controls implemented for one certification provide evidence for others.

| TelsonBase Control | SOC 2 | HIPAA | HITRUST | CJIS | GDPR | SOX |
|-------------------|-------|-------|---------|------|------|-----|
| RBAC (5 roles, 24 permissions) | CC6.1 | 164.312(a)(1) | 01.c | 5.5 | Art. 25 | COSO P12 |
| MFA (TOTP RFC 6238) | CC6.1 | 164.312(d) | 01.b | 5.6.2.2 | Art. 32 | COSO P12 |
| SHA-256 audit chain | CC7.2 | 164.312(b) | 09.aa | 5.4.1 | Art. 30 | COSO P16 |
| AES-256-GCM encryption | CC6.7 | 164.312(a)(2)(iv) | 06.d | 5.10.1.2 | Art. 32 | COSO P13 |
| TLS 1.2+ transport | CC6.7 | 164.312(e)(1) | 09.m | 5.10.1.1 | Art. 32 | -- |
| Session management | CC6.1 | 164.312(a)(2)(iii) | 01.t | 5.5.5 | Art. 25 | COSO P12 |
| Breach notification | CC7.3 | 164.404 | 11.a | 5.3 | Art. 33 | -- |
| Data retention | CC7.4 | 164.530(j) | 01.a | 5.8 | Art. 5(1)(e) | -- |
| Network segmentation | CC6.6 | 164.310(a)(1) | 08.a | 5.10.1 | Art. 32 | -- |
| Training program | CC1.4 | 164.308(a)(5) | 02.e | 5.2 | Art. 39 | -- |
| Incident response | CC7.3, CC7.4 | 164.308(a)(6) | 11.a | 5.3 | Art. 33-34 | -- |
| Data classification | CC6.7 | 164.312(a)(1) | 07.a | 5.8 | Art. 5(1)(c) | COSO P13 |

Every control listed above is implemented in TelsonBase today. The primary gap across all frameworks is procedural documentation and formal third-party validation, not technical implementation.

---

## XIII. Risk Register: Certification Blockers

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| No formal HIPAA SRA conducted | Cannot demonstrate HIPAA compliance to covered entity clients | High | Phase 2 -- engage assessor in months 1-2 |
| SOC 2 Type II requires 6-month observation period | Cannot accelerate enterprise sales timeline | High | Begin observation period as early as possible (month 3) |
| FIPS 140-2 gap blocks CJIS compliance | Cannot serve criminal defense / law enforcement clients | Medium | Phase 5 -- FIPS Docker build (only if market demands) |
| Fernet uses AES-128-CBC (not AES-256) | May be flagged in audits as weaker than AES-256-GCM used elsewhere | Low | Replace Fernet with AES-256-GCM for MFA secrets (engineering task) |
| pip-audit: 16 CVEs in 8 packages | Auditors will flag known vulnerabilities in dependency chain | Medium | Remediate CVEs before SOC 2 Type II observation period begins |
| Bandit finding: tarfile.extractall | CWE-22 path traversal in backup_agent.py | Low | Remediate with safe extraction wrapper |
| No formal change management policy | SOC 2 CC8.1 requires documented change management | Medium | Draft policy document (1-2 days effort) |
| No formal vendor management policy | SOC 2 requires vendor risk assessment | Medium | Draft policy document, maintain vendor inventory |

---

## XIV. Annual Maintenance After Initial Certification

| Activity | Frequency | Estimated Cost |
|----------|-----------|---------------|
| SOC 2 Type II re-audit | Annual | $15-35K |
| HITRUST CSF re-assessment | Biennial (every 2 years) | $10-20K |
| HIPAA Security Risk Assessment | Annual | $3-10K |
| Penetration test | Annual | $5-15K |
| Vulnerability scanning | Continuous (quarterly reporting) | $1-5K |
| Compliance officer oversight | Ongoing | $5-15K/year |
| **Total annual maintenance** | | **$25-75K/year** |

---

## XV. Related Documents

- [Legal Compliance](LEGAL_COMPLIANCE.md) -- Regulatory compliance mapping for real estate and legal markets
- [Healthcare Compliance](HEALTHCARE_COMPLIANCE.md) -- HIPAA/HITECH/HITRUST control mapping and implementation details
- [Encryption at Rest](ENCRYPTION_AT_REST.md) -- Encryption posture, shared responsibility model, customer implementation guide
- [Security Architecture](SECURITY_ARCHITECTURE.md) -- Full security layer overview (10 layers)
- [Incident Response](INCIDENT_RESPONSE.md) -- Incident response plan with severity levels and procedures
- [Backup and Recovery](BACKUP_RECOVERY.md) -- Backup procedures, RPO/RTO targets
- [Disaster Recovery](DISASTER_RECOVERY.md) -- Recovery procedures, contingency plan testing
- [Secrets Management](SECRETS_MANAGEMENT.md) -- Key management, rotation, Docker secrets

---

*This document is intended for executive leadership, compliance officers, and security assessors evaluating TelsonBase's certification roadmap. It provides a phased, budget-aware path to achieving the compliance certifications required for enterprise law firm sales, healthcare-adjacent practice support, and regulated industry deployment. For technical implementation details, refer to the referenced source files and companion compliance documents.*

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
