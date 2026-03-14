# ClawCoat -- SOC 2 Type I Report Documentation

**Version:** v11.0.1 · **Maintainer:** Quietfire AI · **Classification:** Auditor-Ready Documentation

---

## 1. Management Assertion Statement

The management of TelsonBase asserts that the accompanying description of the TelsonBase Zero-Trust AI Agent Security Platform, version v11.0.1, fairly presents the system as designed and implemented as of March 8, 2026. The description includes the principal service commitments and system requirements, and the controls stated in the description were suitably designed to provide reasonable assurance that the principal service commitments and system requirements would be achieved based on the applicable Trust Service Criteria set forth in TSP Section 100, 2017 Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy (AICPA, Trust Services Criteria), if the controls operated effectively throughout the specified period, and if the complementary user entity controls and complementary subservice organization controls described herein operated effectively throughout the specified period.

This assertion covers TelsonBase as an open-source, self-hosted platform. Management makes no assertion regarding any individual deployment of TelsonBase, which remains entirely under the control of the deploying organization. See `DISCLAIMER.md` for the full limitation of liability applicable to this software.

**Responsible Party:** Jeff Phillips, Architect and Principal
**Contact:** security@clawcoat.com
**Date of Assertion:** March 6, 2026

---

## 2. System Description

### 2.1 System Purpose

TelsonBase is a zero-trust AI agent security platform that provides secure orchestration of autonomous AI agents for professional services organizations, with primary markets in legal and real estate. The platform enforces cryptographic provenance on all agent communications, implements multi-tenant client-matter isolation, and maintains compliance infrastructure for HIPAA, HITECH, HITRUST, and CJIS regulatory frameworks.

### 2.2 System Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Application Server | FastAPI (Python), Uvicorn | Core API and business logic |
| Database | PostgreSQL 16 | Persistent structured data (users, audit entries, tenants, compliance records) |
| Cache / State Store | Redis | Session state, rate limiting counters, audit chain entries, encrypted secrets |
| Message Broker | Mosquitto (MQTT) | Inter-agent publish/subscribe messaging |
| AI Inference | Ollama | Local LLM inference (no external API calls) |
| Reverse Proxy / TLS | Traefik | HTTPS termination, HSTS, security headers |
| Monitoring | Prometheus + Grafana | Metrics collection, dashboards, alerting |
| Task Queue | Celery (Redis broker) | Asynchronous task execution |
| Agent Interface | MCP gateway (`/mcp`) | Goose / Claude Desktop integration - operator-authenticated, HITL-gated |
| Container Runtime | Docker Compose | Service orchestration and health management |

### 2.3 System Boundaries

TelsonBase is a self-hosted platform deployed on customer-controlled infrastructure (on-premises servers, NAS devices, or private cloud). The system boundary encompasses:

- **In scope:** All application code, Docker containers, inter-container networking, API endpoints, authentication and authorization subsystems, audit chain, encryption modules, compliance modules, monitoring stack, and backup/restore tooling.
- **Out of scope:** Customer network infrastructure, physical security of hosting hardware, volume-level disk encryption (customer responsibility), DNS and domain management, email delivery infrastructure, end-user devices and browsers.

### 2.4 Deployment Model

Self-hosted, single-node Docker Compose deployment. All services run on the customer's infrastructure. No data leaves the customer's network. This architecture preserves attorney-client privilege and satisfies data residency requirements for legal and healthcare use cases.

### 2.5 Principal Service Commitments

1. Maintain cryptographic integrity of all agent communication and audit records.
2. Enforce role-based access control with least-privilege permissions.
3. Provide multi-tenant isolation with client-matter boundaries.
4. Support regulatory compliance for HIPAA, CJIS, and SOC 2 frameworks.
5. Enable customer-controlled backup and disaster recovery within defined RPO/RTO targets.

---

## 3. Control Environment Summary

### 3.1 Governance

TelsonBase maintains a documented production hardening roadmap tracked via GitHub Issues. Engineering decisions follow a defined working agreement documented in `CONTRIBUTING.md`. All code changes are subject to automated CI/CD testing via GitHub Actions (`.github/workflows/ci.yml`) with 720 tests (96 security, 115 QMS, 129 tool governance, 55 OpenClaw, 29 end-to-end, 7 contract, 289 core).

### 3.2 Security Program

The security program is implemented across 9 dedicated security modules in the `core/` directory, with 96 security-focused tests (`tests/test_security_battery.py`) and 27 end-to-end integration tests (`tests/test_e2e_integration.py`). Security controls include authentication, authorization, session management, MFA, audit logging, rate limiting, encryption, and error sanitization.

### 3.3 Personnel

Access to the TelsonBase codebase and production infrastructure is restricted. The RBAC system enforces five distinct roles (admin, manager, operator, analyst, viewer) with granular permissions mapped to all 140+ API endpoints.

### 3.4 Monitoring and Incident Response

Prometheus collects application metrics. Grafana provides dashboards and alerting with predefined alert rules for high error rates, high latency, authentication failure spikes, audit chain integrity failures, and service availability. Incident response procedures are documented in `docs/INCIDENT_RESPONSE.md`.

---

## 4. Risk Assessment Approach

### 4.1 Methodology

TelsonBase employs a threat-driven risk assessment approach:

1. **Asset identification:** All data stores (PostgreSQL, Redis), secrets (encryption keys, API keys, JWT secrets), and communication channels (API, MQTT, inter-container) are cataloged.
2. **Threat modeling:** The platform's zero-trust architecture assumes all agents and network segments are untrusted. Every agent message requires cryptographic provenance (QMS protocol). Every API call requires authentication and authorization.
3. **Vulnerability management:** Automated security scanning via CI/CD (pip-audit, bandit). Known vulnerabilities are tracked in `CLAUDE.md` under Known Issues.
4. **Control mapping:** Each identified risk is mapped to one or more implemented controls, documented in this report.
5. **Residual risk acceptance:** Risks that cannot be fully mitigated by TelsonBase are assigned to the customer via the Shared Responsibility Model (see Section 9).
6. **Known issues:** Tracked via GitHub Issues. Current open security items include dependency CVEs (pip-audit findings from CI/CD) and a tarfile extraction finding in `backup_agent.py`. All are triaged; none affect the design suitability of the controls in this report.

### 4.2 Risk Register (Summary)

| Risk Category | Primary Controls | Residual Risk Owner |
|--------------|-----------------|-------------------|
| Unauthorized access | MFA, RBAC, session management, account lockout | TelsonBase |
| Data breach | Encryption (Fernet, AES-256-GCM, bcrypt), TLS, network isolation | Shared |
| Audit tampering | SHA-256 hash-linked audit chain, chain verification endpoint | TelsonBase |
| Service interruption | Docker health checks, backup/restore, Prometheus alerting | Shared |
| Regulatory non-compliance | HIPAA modules (12), HITRUST controls, breach notification | Shared |
| Physical security | N/A (self-hosted) | Customer |
| Volume-level encryption | Documented guidance, shared responsibility model | Customer |

---

## 5. Trust Service Criteria -- Security (Common Criteria)

The Security criteria address whether the system is protected against unauthorized access, both physical and logical.

| Control ID | Control Description | TelsonBase Implementation | Evidence Location |
|-----------|-------------------|--------------------------|------------------|
| CC1.1 | Organization demonstrates commitment to integrity and ethical values | Documented working agreement with defined ownership between business and engineering; production hardening roadmap tracked via GitHub Issues | `CONTRIBUTING.md`, GitHub Issues |
| CC2.1 | Information communicated internally to support security objectives | Structured documentation suite covering security architecture, secrets management, encryption, backup/recovery, incident response, and compliance | `docs/SECURITY_ARCHITECTURE.md`, `docs/SECRETS_MANAGEMENT.md`, `docs/INCIDENT_RESPONSE.md` |
| CC3.1 | Risk identification and assessment processes | Threat-driven risk assessment; zero-trust architecture assumes untrusted agents and networks; automated vulnerability scanning in CI/CD; known issues tracked and triaged in GitHub Issues | `.github/workflows/ci.yml`, GitHub Issues |
| CC4.1 | Monitoring of controls | Prometheus metrics collection with Grafana dashboards and alerting (HighErrorRate, HighLatency, AuthFailureSpike, AuditChainBroken, ServiceDown) | `monitoring/prometheus.yml`, `monitoring/prometheus/alerts.yml`, `monitoring/grafana/provisioning/` |
| CC5.1 | Logical access security over system components | RBAC with 5 roles (admin, manager, operator, analyst, viewer) and granular permissions enforced via `require_permission()` decorator on all 140+ endpoints | `core/rbac.py`, `main.py`, `api/security_routes.py`, `api/compliance_routes.py`, `api/tenancy_routes.py` |
| CC5.2 | Authentication mechanisms | Multi-factor authentication (TOTP with backup codes), bcrypt password hashing (12 rounds), account lockout (5 attempts / 15 minutes), password strength validation (12+ characters, mixed case/symbols) | `core/mfa.py`, `core/auth.py`, `core/user_management.py`, `api/auth_routes.py` |
| CC5.3 | Session management | JWT token management with HMAC-SHA256 signing, idle timeout enforcement, HIPAA automatic logoff, session invalidation on logout | `core/session_management.py`, `core/auth_dependencies.py`, `api/auth_routes.py` |
| CC5.4 | API access controls | API key registry, JWT bearer token validation, composable FastAPI dependencies (require_mfa, require_active_session, require_mfa_and_session) | `core/auth_dependencies.py`, `core/auth.py`, `api/security_routes.py` |
| CC6.1 | Encryption of data at rest | Fernet (AES-128-CBC + HMAC-SHA256) for MFA secrets, AES-256-GCM for sensitive Redis fields, bcrypt for passwords, volume-level encryption guidance for customers | `core/secure_storage.py`, `core/mfa.py`, `core/auth.py`, `docs/ENCRYPTION_AT_REST.md` |
| CC6.2 | Encryption of data in transit | TLS termination via Traefik reverse proxy, HSTS headers (1 year, includeSubdomains, preload), HTTP-to-HTTPS redirect | `docker-compose.yml` (Traefik config), `docs/SECURITY_ARCHITECTURE.md` |
| CC6.3 | Cryptographic audit trail | SHA-256 hash-linked audit chain with Redis persistence (configurable max 100K entries), tamper-evident chain verification | `core/audit.py`, `core/persistence.py` |
| CC6.4 | Security headers | SecurityHeadersMiddleware (pure ASGI): X-Content-Type-Options: nosniff, X-Frame-Options: DENY, X-XSS-Protection, Strict-Transport-Security | `core/middleware.py`, `main.py` |
| CC6.5 | Rate limiting | Token bucket rate limiter (300/min, burst 60) at application level; tenant-scoped rate limiting (Redis sliding window, 600/min default per tenant, 120/min per user, premium tier multiplier, in-memory fallback) | `core/middleware.py`, `core/tenant_rate_limiting.py` |
| CC6.6 | Error sanitization | Global exception handler catches all unhandled errors; sanitized responses with no stack traces, file paths, or internal error class names leaked to clients | `main.py`, `core/middleware.py` |
| CC6.7 | Network isolation | Docker internal networks isolate data-tier services (Redis, PostgreSQL) from external access; only Traefik reverse proxy is externally reachable | `docker-compose.yml` |
| CC7.1 | Vulnerability management | Automated CI/CD pipeline with pip-audit (dependency CVE scanning) and bandit (static analysis); known issues tracked and triaged | `.github/workflows/ci.yml`, `CLAUDE.md` (Known Issues) |
| CC7.2 | Automated testing | 720 tests across 7 domains (96 security, 115 QMS, 129 tool governance, 55 OpenClaw, 29 end-to-end, 7 contract, 289 core); pytest executed via `docker compose exec mcp_server python -m pytest tests/ -v`; expected result: 720 passed, 1 skipped, 0 failed | `tests/test_security_battery.py`, `tests/test_e2e_integration.py`, `tests/test_contracts.py`, `.github/workflows/ci.yml` |

---

## 6. Trust Service Criteria -- Availability (A)

The Availability criteria address whether the system is available for operation and use as committed.

| Control ID | Control Description | TelsonBase Implementation | Evidence Location |
|-----------|-------------------|--------------------------|------------------|
| A1.1 | System availability commitments are defined | Recovery objectives documented: RPO 24 hours, RTO 15 minutes. Backup and recovery procedures scripted and tested. | `docs/BACKUP_RECOVERY.md` |
| A1.2 | Container health monitoring | Docker Compose health checks on all services; automatic restart policies; container readiness verification in restore procedure | `docker-compose.yml` |
| A1.3 | Infrastructure monitoring and alerting | Prometheus collects application and infrastructure metrics; Grafana dashboards with auto-provisioned data sources; alert rules for ServiceDown, HighErrorRate, HighLatency | `monitoring/prometheus.yml`, `monitoring/prometheus/alerts.yml`, `monitoring/grafana/provisioning/` |
| A1.4 | Backup procedures | Automated backup script: PostgreSQL pg_dump, Redis BGSAVE + dump.rdb copy, secrets archive, configuration files, manifest with checksums. 30-day retention default. Cron scheduling documented. | `scripts/backup.sh`, `docs/BACKUP_RECOVERY.md` |
| A1.5 | Restore procedures | Scripted restore with confirmation gate (destructive operation warning). Sequence: stop services, restore PostgreSQL, restore Redis, extract secrets, restore config, restart services, health check. Pre-restore backups preserved. | `scripts/restore.sh`, `docs/BACKUP_RECOVERY.md` |
| A1.6 | Data persistence and durability | Redis persistence with RDB snapshots and write-through to sorted sets (configurable max 100K entries). PostgreSQL WAL for crash recovery. 15 modules wired with write-through Redis stores. | `core/persistence.py`, `core/audit.py`, `docker-compose.yml` |
| A1.7 | Auto-recovery on failure | Docker restart policies ensure container auto-recovery. Redis persistence ensures state survival across container restarts. Application reconnection logic for database and cache. | `docker-compose.yml`, `core/persistence.py`, `core/database.py` |
| A1.8 | Disaster recovery documentation | Documented disaster recovery procedures including backup identification, restore execution, post-restore verification, and troubleshooting | `docs/DISASTER_RECOVERY.md`, `docs/BACKUP_RECOVERY.md` |

---

## 7. Trust Service Criteria -- Processing Integrity (PI)

The Processing Integrity criteria address whether system processing is complete, valid, accurate, timely, and authorized.

| Control ID | Control Description | TelsonBase Implementation | Evidence Location |
|-----------|-------------------|--------------------------|------------------|
| PI1.1 | Message provenance and integrity | QMS (Qualified Message Standard) protocol ensures every inter-agent message carries cryptographic provenance. HMAC-SHA256 per-message signatures verify sender identity and message integrity. | `core/qms.py`, `core/signing.py` |
| PI1.2 | Audit chain integrity verification | SHA-256 hash-linked audit chain where each entry references the hash of the previous entry. Dedicated verification endpoint (`/v1/audit/chain/verify`) detects tampering or gaps. Alert rule fires on chain integrity failure. | `core/audit.py`, `main.py` (verify endpoint), `monitoring/prometheus/alerts.yml` (AuditChainBroken) |
| PI1.3 | Input validation | Pydantic models enforce type safety and constraint validation on all API request bodies. FastAPI path and query parameter validation. Structured data models for all database entities. | `core/models.py`, `core/config.py`, `api/auth_routes.py`, `api/compliance_routes.py` |
| PI1.4 | Error handling and sanitization | Global exception handler prevents information leakage. All unhandled exceptions return sanitized error responses. No stack traces, file paths, or internal type names exposed. 8 specific str(e) leaks remediated in Ollama endpoints. n8n integration removed (v8.0.2); replaced by MCP Gateway native integration. | `main.py`, `core/middleware.py` |
| PI1.5 | Human-in-the-loop approval gates | HITL approval gates enforce human authorization on all destructive and external actions before agent execution. Prevents unauthorized autonomous operations. | `core/approval.py` |
| PI1.6 | Data integrity in persistence | PostgreSQL ACID transactions for structured data. Redis write-through pattern ensures dual-write consistency. Backup manifest includes file sizes for verification of backup completeness. | `core/database.py`, `core/persistence.py`, `scripts/backup.sh` |
| PI1.7 | Schema migration integrity | Alembic database migrations with versioned scripts. Initial schema defines 4 tables (users, audit_entries, tenants, compliance_records). Runtime DATABASE_URL from configuration. | `alembic/env.py`, `alembic/versions/001_initial_schema.py` |

---

## 8. Trust Service Criteria -- Confidentiality (C)

The Confidentiality criteria address whether information designated as confidential is protected as committed.

| Control ID | Control Description | TelsonBase Implementation | Evidence Location |
|-----------|-------------------|--------------------------|------------------|
| C1.1 | Multi-tenant data isolation | Client-matter isolation enforces strict boundaries between tenants. Each tenant's data is logically separated. Tenant-scoped queries prevent cross-tenant data access. | `core/tenancy.py`, `api/tenancy_routes.py` |
| C1.2 | Litigation hold management | Litigation holds prevent destruction of data subject to legal preservation obligations. Hold creation, release, and tracking through dedicated endpoints. | `core/legal_hold.py`, `api/compliance_routes.py` |
| C1.3 | Encryption of secrets at rest | MFA secrets encrypted with Fernet (AES-128-CBC + HMAC-SHA256) via SecureRedisStore. Sensitive Redis fields encrypted with AES-256-GCM via SecureStorageManager (PBKDF2-derived key). | `core/secure_storage.py`, `core/mfa.py` |
| C1.4 | Password protection | Passwords hashed with bcrypt (12 rounds). One-way hash; passwords are never stored in reversible form. Password strength validation enforces 12+ character minimum with complexity requirements. | `core/auth.py`, `core/user_management.py` |
| C1.5 | Volume-level encryption guidance | Documented recommendations for LUKS (Linux), BitLocker (Windows), FileVault (macOS), and NAS-specific encryption. Shared responsibility model clearly delineates customer obligation. | `docs/ENCRYPTION_AT_REST.md` |
| C1.6 | Data classification | Data classification module categorizes information by sensitivity level, enabling appropriate handling and access controls based on classification. | `core/data_classification.py` |
| C1.7 | Secrets management | Automated secrets generation with rotation support (--rotate flag). Production validators enforce non-default secrets at startup. Secrets stored in dedicated directory, separate from application code. | `scripts/generate_secrets.sh`, `core/config.py`, `core/secrets.py`, `docs/SECRETS_MANAGEMENT.md` |
| C1.8 | Network-level confidentiality | TLS termination via Traefik for all external traffic. Internal Docker networks marked as `internal: true` to prevent external access to data-tier services. Redis requirepass authentication enforced. | `docker-compose.yml`, `docs/ENCRYPTION_AT_REST.md` |
| C1.9 | Federation payload encryption | Cross-instance federation payloads encrypted with AES-256-GCM session keys and signed with RSA-4096 identity keys. Mutual TLS available for federation channels. | `federation/trust.py`, `federation/mtls.py` |

---

## 9. Trust Service Criteria -- Privacy (P)

The Privacy criteria address whether personal information is collected, used, retained, disclosed, and disposed of in conformity with commitments and applicable criteria.

| Control ID | Control Description | TelsonBase Implementation | Evidence Location |
|-----------|-------------------|--------------------------|------------------|
| P1.1 | PHI de-identification | De-identification module removes or obscures protected health information from datasets before processing or disclosure. Supports Safe Harbor and Expert Determination methods. | `core/phi_deidentification.py` |
| P1.2 | Minimum necessary access | Minimum necessary access module restricts PHI access to the minimum information required to accomplish the intended purpose, per HIPAA Minimum Necessary Standard (45 CFR 164.502(b)). | `core/minimum_necessary.py` |
| P1.3 | PHI disclosure tracking | Disclosure tracking module maintains a log of all PHI disclosures, enabling accounting of disclosures as required by HIPAA (45 CFR 164.528). Supports right to accounting of disclosures. | `core/phi_disclosure.py`, `api/compliance_routes.py` |
| P1.4 | Breach notification | Breach notification module implements the HIPAA Breach Notification Rule. 72-hour assessment window for determining whether a breach is reportable. Tracks breach investigations, affected individuals, and notification status. | `core/breach_notification.py`, `api/compliance_routes.py` |
| P1.5 | Data retention policies | Data retention module enforces configurable retention periods. Automated identification of data eligible for destruction. Litigation holds override retention-based deletion. | `core/data_retention.py`, `api/compliance_routes.py` |
| P1.6 | Role-based access to personal information | RBAC enforcement (5 roles with granular permissions) limits access to personal information based on job function. Permission categories include view, manage, admin, and security scopes. | `core/rbac.py`, `core/auth_dependencies.py` |
| P1.7 | Consent and authorization tracking | Compliance module tracks consent and authorization for data processing activities. Business Associate Agreement (BAA) tracking for covered entity relationships. | `core/baa_tracking.py`, `core/compliance.py`, `api/compliance_routes.py` |
| P1.8 | Sanctions and workforce compliance | Sanctions module tracks workforce compliance violations and enforces disciplinary actions for privacy policy violations, per HIPAA Administrative Safeguards (45 CFR 164.308(a)(1)(ii)(C)). | `core/sanctions.py`, `api/compliance_routes.py` |
| P1.9 | Privacy training tracking | Training module tracks workforce privacy and security training completion, ensuring all personnel with access to PHI or PII have completed required training. | `core/training.py`, `api/compliance_routes.py` |
| P1.10 | Emergency access procedures | Emergency access module provides break-glass procedures for accessing PHI in emergencies, with full audit logging of emergency access events. | `core/emergency_access.py`, `api/security_routes.py` |

---

## 10. Complementary User Entity Controls (CUECs)

TelsonBase operates under a shared responsibility model. The following controls must be implemented by the customer (the User Entity) for the system's security objectives to be met. Failure to implement these controls may result in the overall security posture being materially weakened.

### 10.1 Infrastructure Security

| CUEC ID | Control Requirement | Rationale |
|---------|-------------------|-----------|
| CUEC-1 | Enable volume-level encryption (LUKS, BitLocker, FileVault, or NAS encryption) on all storage volumes hosting TelsonBase Docker volumes. | TelsonBase encrypts sensitive fields at the application level but does not encrypt entire databases or all data on disk. Volume encryption is required for full encryption-at-rest coverage. |
| CUEC-2 | Restrict physical access to the server or NAS device hosting TelsonBase to authorized personnel only. | TelsonBase is self-hosted. Physical access to the hardware bypasses all logical access controls. |
| CUEC-3 | Configure host-level firewall rules to restrict network access to TelsonBase services. Only port 443 (HTTPS via Traefik) should be externally accessible. | Docker networking isolates internal services, but host-level firewall rules are the customer's responsibility. |
| CUEC-4 | Maintain the host operating system with current security patches. | TelsonBase runs in Docker containers but depends on the host OS kernel and Docker runtime. |

### 10.2 Operational Security

| CUEC ID | Control Requirement | Rationale |
|---------|-------------------|-----------|
| CUEC-5 | Execute the backup script (`scripts/backup.sh`) on a daily schedule (recommended: cron at 02:00). | TelsonBase provides the backup tooling but does not enforce backup execution. The RPO of 24 hours requires daily backups. |
| CUEC-6 | Copy backups to offsite storage (NAS, S3, or equivalent). | The backup script stores backups locally. Offsite copies are required for disaster recovery. |
| CUEC-7 | Test the restore procedure (`scripts/restore.sh`) at least quarterly. | Untested backups are not reliable backups. The customer must verify restore capability. |
| CUEC-8 | Monitor Grafana alerting channels and respond to fired alerts within defined SLA. | TelsonBase configures alert rules but does not operate a 24/7 NOC. The customer must monitor and respond. |
| CUEC-9 | Store encryption keys and recovery keys in a secure location separate from the encrypted data. | Key management for volume encryption is the customer's responsibility. Loss of keys means loss of data. |

### 10.3 Access Management

| CUEC ID | Control Requirement | Rationale |
|---------|-------------------|-----------|
| CUEC-10 | Provision user accounts with the least-privilege role sufficient for the user's job function. | TelsonBase enforces RBAC but the customer assigns roles. Over-provisioning undermines the control. |
| CUEC-11 | Require all users to complete MFA enrollment before accessing production data. | TelsonBase provides MFA infrastructure but enrollment is a user action. |
| CUEC-12 | Review user access quarterly and revoke accounts for terminated or transferred personnel. | TelsonBase does not have visibility into HR events. The customer must manage the user lifecycle. |
| CUEC-13 | Change all default secrets before production deployment using `scripts/generate_secrets.sh`. | TelsonBase warns on default secrets at startup but cannot force secret rotation. |

### 10.4 Compliance

| CUEC ID | Control Requirement | Rationale |
|---------|-------------------|-----------|
| CUEC-14 | Execute a Business Associate Agreement (BAA) with TelsonBase (or the deploying MSP) before processing PHI. | HIPAA requires BAAs between covered entities and business associates. TelsonBase provides BAA tracking infrastructure but the legal agreement is the customer's responsibility. |
| CUEC-15 | Complete workforce HIPAA privacy and security training annually. | TelsonBase tracks training completion but does not deliver training content. |
| CUEC-16 | Notify TelsonBase support within 24 hours of a suspected security incident involving the platform. | Timely incident response requires prompt notification. |

---

## 11. Complementary Subservice Organization Controls (CSOCs)

TelsonBase's self-hosted architecture minimizes reliance on subservice organizations. The following external dependencies exist:

| Subservice Organization | Service Provided | Control Expectation |
|------------------------|-----------------|-------------------|
| Let's Encrypt | TLS certificate issuance | Availability of ACME protocol for automated certificate renewal. Customer may substitute their own CA. |
| Docker Hub | Container image registry | Integrity of base images (python, postgres, redis, traefik). Images are pinned to specific versions in `docker-compose.yml`. |
| GitHub | Source code repository and CI/CD | Access controls on the repository. Branch protection rules. Automated test execution on pull requests. |

No customer data is transmitted to any subservice organization during normal operation.

---

## 12. Description of Tests of Controls (Type I Scope)

A SOC 2 Type I report evaluates the suitability of design of controls at a specific point in time. The following evidence artifacts are available for auditor inspection to verify that controls are suitably designed as of the report date.

### 12.1 Available Evidence Artifacts

| Artifact | Location | Description |
|----------|---------|-------------|
| Automated test suite results | `tests/` directory, CI/CD logs | 720 tests (96 security, 115 QMS, 129 tool governance, 55 OpenClaw, 29 E2E, 7 contract, 289 core) with pass/fail results |
| Security battery tests | `tests/test_security_battery.py` | 96 tests covering authentication, authorization, session management, MFA, encryption, error sanitization, and runtime boundaries |
| End-to-end integration tests | `tests/test_e2e_integration.py` | 29 tests across 6 test classes: UserLifecycle, TenantWorkflow, TenantIsolation, SecurityEndpoints, AuditChainIntegrity, ErrorSanitization |
| RBAC permission matrix | `core/rbac.py` | 5 roles with enumerated permissions; `require_permission()` decorator applied to 140+ endpoints |
| Audit chain verification | `core/audit.py`, `/v1/audit/chain/verify` endpoint | SHA-256 hash-linked chain with programmatic integrity verification |
| Encryption implementation | `core/secure_storage.py`, `core/mfa.py`, `core/auth.py` | Fernet, AES-256-GCM, bcrypt implementations with key derivation |
| Backup/restore scripts | `scripts/backup.sh`, `scripts/restore.sh` | Scripted procedures with manifest verification |
| Monitoring configuration | `monitoring/prometheus/alerts.yml` | 5 predefined alert rules with thresholds |
| Docker Compose configuration | `docker-compose.yml` | Service definitions, health checks, network isolation, restart policies |
| CI/CD pipeline | `.github/workflows/ci.yml` | Automated testing, Docker build, and security scanning |
| Compliance module inventory | `core/` directory (12 compliance modules) | legal_hold, breach_notification, data_retention, sanctions, training, contingency_testing, baa_tracking, hitrust_controls, phi_disclosure, phi_deidentification, minimum_necessary, compliance |
| Security architecture documentation | `docs/SECURITY_ARCHITECTURE.md` | Multi-layer security architecture description |
| Secrets management documentation | `docs/SECRETS_MANAGEMENT.md` | Secret generation, rotation, and validation procedures |
| Encryption at rest documentation | `docs/ENCRYPTION_AT_REST.md` | Encryption posture, shared responsibility model, implementation checklist |
| Incident response documentation | `docs/INCIDENT_RESPONSE.md` | Incident classification, response procedures, escalation paths |

### 12.2 Auditor Notes

1. **Type I vs. Type II:** This document supports a Type I assessment (design effectiveness at a point in time). A Type II assessment (operating effectiveness over a period) would require production operational evidence including log samples, access review records, backup execution logs, incident response records, and change management records collected over a minimum 3-month observation period.

2. **Self-hosted model:** Because TelsonBase is deployed on customer infrastructure, certain controls (physical security, volume encryption, network security) are the customer's responsibility. The Complementary User Entity Controls (Section 10) must be evaluated in conjunction with TelsonBase's controls.

3. **Known issues:** Tracked via GitHub Issues. Current items include dependency CVEs surfaced by pip-audit in CI/CD and one bandit finding (tarfile extraction in `backup_agent.py`). All are tracked and triaged; none affect the design suitability of the controls described in this report. Remediation status should be verified in a Type II engagement.

---

## 13. Control Cross-Reference Matrix

The following matrix maps TelsonBase controls to the AICPA 2017 Trust Services Criteria point of focus areas.

| TSC Reference | Point of Focus | Mapped Control IDs |
|--------------|---------------|-------------------|
| CC1.1 | Integrity and ethical values | CC1.1 |
| CC2.1 | Internal communication | CC2.1 |
| CC3.1 | Risk identification | CC3.1 |
| CC4.1 | Monitoring activities | CC4.1, A1.3 |
| CC5.1--CC5.4 | Logical access controls | CC5.1, CC5.2, CC5.3, CC5.4 |
| CC6.1 | Encryption at rest | CC6.1, C1.3, C1.4, C1.5 |
| CC6.2--CC6.3 | Encryption in transit, integrity | CC6.2, CC6.3 |
| CC6.4--CC6.7 | Protective controls | CC6.4, CC6.5, CC6.6, CC6.7 |
| CC7.1--CC7.2 | Vulnerability management and testing | CC7.1, CC7.2 |
| A1.1--A1.8 | Availability controls | A1.1 through A1.8 |
| PI1.1--PI1.7 | Processing integrity controls | PI1.1 through PI1.7 |
| C1.1--C1.9 | Confidentiality controls | C1.1 through C1.9 |
| P1.1--P1.10 | Privacy controls | P1.1 through P1.10 |

---

## 14. Document Control

| Field | Value |
|-------|-------|
| Document Title | TelsonBase SOC 2 Type I -- Trust Service Criteria Control Mapping |
| Version | 1.2 |
| Date | March 8, 2026 |
| Classification | Auditor-Ready Documentation |
| Platform Version | v11.0.1 |
| Author | Jeff Phillips, Architect - Quietfire AI |
| Review Status | Updated for public release -- pending independent auditor review |
| Next Review | Prior to Type II engagement or upon material system change |

---

## Related Documents

- [Security Architecture](SECURITY_ARCHITECTURE.md) -- Multi-layer security architecture
- [Encryption at Rest](ENCRYPTION_AT_REST.md) -- Encryption posture and shared responsibility
- [Backup and Recovery](BACKUP_RECOVERY.md) -- RPO/RTO targets and procedures
- [Disaster Recovery](DISASTER_RECOVERY.md) -- Full recovery procedures
- [Secrets Management](SECRETS_MANAGEMENT.md) -- Secret lifecycle management
- [Incident Response](INCIDENT_RESPONSE.md) -- Incident handling procedures
- [Legal Compliance](LEGAL_COMPLIANCE.md) -- Regulatory compliance mapping
- [Healthcare Compliance](HEALTHCARE_COMPLIANCE.md) -- HIPAA/HITECH/HITRUST guidance
- [Disclaimer and Terms of Use](../../DISCLAIMER.md) -- Limitation of liability, no warranty, AI platform disclaimer

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
