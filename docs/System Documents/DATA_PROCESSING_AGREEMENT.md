# Data Processing Agreement

**TelsonBase Zero-Trust AI Agent Security Platform**

---

**Version:** 1.0
**Last Updated:** March 8, 2026
**Document Classification:** CONFIDENTIAL -- Legal Template

---

## PARTIES

This Data Processing Agreement ("DPA") is entered into as of [EFFECTIVE DATE] ("Effective Date") by and between:

**Data Controller:**
[CUSTOMER NAME], a [ENTITY TYPE] organized under the laws of [JURISDICTION], with its principal office at [CUSTOMER ADDRESS] ("Controller" or "Customer").

**Data Processor:**
Quietfire AI, doing business as TelsonBase ("Processor" or "TelsonBase").

Controller and Processor are each a "Party" and collectively the "Parties."

This DPA is incorporated into and forms part of the Master Service Agreement or Software License Agreement between the Parties dated [MSA DATE] ("Service Agreement") under which TelsonBase provides the Controller with a self-hosted, zero-trust AI agent security platform (the "Platform").

---

## 1. DEFINITIONS

**1.1 "Applicable Data Protection Law"** means all laws and regulations relating to the processing and protection of Personal Data applicable to the performance of this DPA, including but not limited to: the General Data Protection Regulation (EU) 2016/679 ("GDPR"); the California Consumer Privacy Act ("CCPA") as amended by the California Privacy Rights Act ("CPRA"); applicable state privacy laws; and any implementing or supplementary legislation.

**1.2 "Personal Data"** means any information relating to an identified or identifiable natural person ("Data Subject"), including but not limited to names, contact information, identification numbers, case or matter details, financial records, and protected health information, to the extent such data is processed by the Platform within the Controller's infrastructure.

**1.3 "Processing"** means any operation or set of operations performed on Personal Data, whether or not by automated means, including collection, recording, organization, structuring, storage, adaptation, alteration, retrieval, consultation, use, disclosure by transmission, dissemination, alignment, combination, restriction, erasure, or destruction.

**1.4 "Data Subject"** means an identified or identifiable natural person to whom Personal Data relates.

**1.5 "Sub-processor"** means any third party engaged by the Processor to process Personal Data on behalf of the Controller.

**1.6 "Security Incident"** means any breach of security leading to the accidental or unlawful destruction, loss, alteration, unauthorized disclosure of, or access to, Personal Data transmitted, stored, or otherwise processed by the Platform.

**1.7 "Self-Hosted Deployment"** means the deployment model under which the Platform operates entirely on infrastructure owned, leased, or controlled by the Controller, with no Personal Data transmitted to or stored on infrastructure owned or controlled by the Processor.

**1.8 "Audit Chain"** means the cryptographic, hash-linked audit log maintained by the Platform using SHA-256 chaining, which provides a tamper-evident record of all security-relevant events.

**1.9 "Client-Matter Isolation"** means the logical separation of data within the Platform by tenant, client, and matter, enforced through namespaced storage keys, role-based access controls, and litigation hold mechanisms.

---

## 2. SCOPE AND PURPOSE OF PROCESSING

**2.1 Purpose.** The Processor provides the Controller with a self-hosted, zero-trust AI agent security platform designed for law firms and real estate brokerages. The Platform enables AI agent orchestration, document management, compliance tracking, audit logging, and multi-tenant data isolation.

**2.2 Self-Hosted Architecture.** The Platform operates under a Self-Hosted Deployment model. All Personal Data processed by the Platform remains on infrastructure owned or controlled by the Controller at all times. The Processor does not receive, access, store, or transmit Personal Data in the ordinary course of providing the Platform. No Personal Data is sent to external AI services for inference or model training; all AI inference occurs locally via Ollama within the Controller's network.

**2.3 Processor Role.** The Processor's role is limited to:
- (a) Providing the Platform software, updates, and patches;
- (b) Providing documentation, configuration guidance, and technical support;
- (c) Providing security advisories and compliance documentation.

**2.4 No Remote Access.** The Processor does not maintain persistent or on-demand remote access to the Controller's deployment unless explicitly authorized in writing by the Controller for a specific support engagement, subject to the terms of Section 5.2.

---

## 3. DATA PROCESSING DETAILS

### 3.1 Categories of Data Subjects

The following categories of Data Subjects may have their Personal Data processed by the Platform, depending on the Controller's use case:

| Category | Description |
|----------|-------------|
| **Employees and Staff** | Attorneys, paralegals, administrative staff, IT personnel, and other employees of the Controller |
| **Clients** | Individuals and representatives of entities that are clients of the Controller |
| **Opposing Parties** | Individuals and representatives of entities that are adverse parties in legal matters |
| **Witnesses** | Individuals identified as witnesses in legal proceedings or transactions |
| **Third-Party Contacts** | Experts, consultants, co-counsel, judges, clerks, and other individuals referenced in matters |

### 3.2 Types of Personal Data

The following types of Personal Data may be processed by the Platform:

| Data Type | Examples |
|-----------|----------|
| **Identity Data** | Names, aliases, dates of birth, government-issued identification numbers |
| **Contact Data** | Addresses, email addresses, telephone numbers, facsimile numbers |
| **Case and Matter Data** | Case numbers, matter descriptions, legal strategies, privileged communications, work product |
| **Financial Data** | Billing records, trust account information, settlement amounts, transaction details |
| **Protected Health Information (PHI)** | Medical records, treatment information, health insurance data (where the Controller handles healthcare-adjacent legal matters) |
| **Authentication Data** | Usernames, hashed passwords, MFA secrets (encrypted), session tokens |
| **Behavioral Data** | Platform activity logs, audit trail entries, access timestamps |

### 3.3 Processing Activities

The Platform performs the following processing activities on Personal Data:

| Activity | Description |
|----------|-------------|
| **Storage** | Persistent storage in PostgreSQL and Redis within the Controller's infrastructure |
| **Indexing** | Organizing data by tenant, client, and matter for retrieval and isolation |
| **Audit Logging** | Recording security-relevant events in a cryptographic, tamper-evident audit chain |
| **Compliance Tracking** | Monitoring legal holds, retention policies, breach assessments, and regulatory obligations |
| **Access Control Enforcement** | Authenticating users, enforcing role-based permissions, managing sessions |
| **AI Agent Orchestration** | Routing data through locally hosted AI inference models for document analysis and workflow automation |
| **Encryption** | Encrypting sensitive fields at the application level before storage |

### 3.4 Duration of Processing

Processing shall continue for the duration of the Service Agreement. Upon termination or expiration, the provisions of Section 9 (Term and Termination) shall apply.

---

## 4. PROCESSOR OBLIGATIONS

**4.1 Processing on Instructions.** The Processor shall process Personal Data only in accordance with the Controller's documented instructions as set forth in this DPA and the Service Agreement. The Platform's processing logic is defined by its software configuration, which is deployed and controlled by the Controller on its own infrastructure. The Processor shall not process Personal Data for any purpose other than providing and supporting the Platform as described herein.

**4.2 Confidentiality.** The Processor shall ensure that all personnel authorized to process Personal Data have committed themselves to confidentiality obligations or are under an appropriate statutory obligation of confidentiality. The Processor shall limit access to Personal Data to those personnel who require such access to perform obligations under the Service Agreement.

**4.3 Security Measures.** The Processor shall implement and maintain appropriate technical and organizational security measures as described in Section 6 (Security Measures) of this DPA. These measures are designed to protect Personal Data against unauthorized or unlawful processing, accidental loss, destruction, or damage.

**4.4 Sub-processor Management.**

(a) **Self-Hosted Deployment.** Under the standard Self-Hosted Deployment model, the Processor does not engage Sub-processors to process Personal Data. All data processing occurs on the Controller's infrastructure using the Processor's software.

(b) **Support Engagements.** If the Controller authorizes the Processor to access its deployment for technical support purposes, the Processor shall not engage any Sub-processor to perform such support without prior written consent of the Controller.

(c) **Notification.** If the Processor determines that a Sub-processor engagement is necessary for any reason, the Processor shall notify the Controller in writing at least thirty (30) days in advance, providing the identity of the proposed Sub-processor, the nature of the processing, and the safeguards in place. The Controller shall have the right to object to such engagement.

**4.5 Data Subject Rights.** The Processor shall provide reasonable assistance to the Controller in responding to requests from Data Subjects exercising their rights under Applicable Data Protection Law, including rights of access, rectification, erasure, restriction, data portability, and objection. The Platform provides the following capabilities to support Data Subject rights:

| Right | Platform Capability |
|-------|-------------------|
| **Access** | Data export via API endpoints; audit chain export for compliance (`export_chain_for_compliance()`) |
| **Rectification** | Data modification through authenticated API operations with full audit trail |
| **Erasure** | CCPA-compliant deletion workflow with approval gates, legal hold checks, and audit logging of deletion events (without retaining deleted data) |
| **Restriction** | User deactivation, session invalidation, and matter-level access controls |
| **Portability** | Structured data export in machine-readable format via API |
| **Objection** | Configurable processing scopes; ability to disable specific processing features per tenant |

**4.6 Data Breach Notification.**

(a) The Processor shall notify the Controller without undue delay upon becoming aware of a Security Incident affecting Personal Data processed by the Platform.

(b) The Platform includes a built-in breach assessment engine (`core/breach_notification.py`) that provides:
- Severity classification (Critical, High, Medium, Low);
- Automated notification requirement determination based on exposed data types;
- Notification deadline tracking per applicable state law (30-60 day windows);
- Overdue notification detection and alerting;
- Full audit trail of all breach-related activities.

(c) The Platform's breach assessment workflow operates on a 72-hour assessment window from the time of detection, during which the Controller shall:
- (i) Classify the severity of the incident;
- (ii) Determine the scope of affected data and Data Subjects;
- (iii) Assess containment status;
- (iv) Determine notification obligations under applicable law.

(d) For Security Incidents involving vulnerabilities in the Platform software itself, the Processor shall:
- (i) Notify the Controller within twenty-four (24) hours of confirming the vulnerability;
- (ii) Provide a severity assessment and recommended remediation steps;
- (iii) Issue a patch or update within a commercially reasonable timeframe;
- (iv) Provide a post-incident report detailing root cause, impact, and preventive measures.

**4.7 Assistance with Compliance.** The Processor shall provide reasonable assistance to the Controller in ensuring compliance with the Controller's obligations under Applicable Data Protection Law, including with respect to data protection impact assessments and prior consultations with supervisory authorities.

**4.8 Return and Deletion of Data.** Upon termination or expiration of the Service Agreement, the Processor shall, at the Controller's election:
- (a) Assist the Controller in exporting all Personal Data in a structured, machine-readable format; or
- (b) Provide documentation and procedures for the Controller to securely delete all Personal Data from the Platform.

Because the Platform operates under a Self-Hosted Deployment model, all data resides on the Controller's infrastructure. The Controller retains full control over data retention and deletion at all times. The Processor does not retain any copies of Personal Data.

---

## 5. CONTROLLER OBLIGATIONS

**5.1 Lawful Basis.** The Controller shall ensure that it has a lawful basis for the processing of Personal Data under Applicable Data Protection Law, including obtaining any required consents from Data Subjects and providing any required notices.

**5.2 Data Minimization.** The Controller shall ensure that only Personal Data that is adequate, relevant, and limited to what is necessary for the purposes of processing is entered into the Platform. The Controller shall configure the Platform's data classification features (`core/data_classification.py`) to appropriately categorize data by sensitivity level (Public, Internal, Confidential, Restricted).

**5.3 Infrastructure Security.** Under the shared responsibility model, the Controller is responsible for securing the infrastructure on which the Platform operates. This includes:

| Responsibility | Description |
|---------------|-------------|
| **Volume Encryption** | Enabling full-disk or full-volume encryption (LUKS, BitLocker, FileVault, or NAS-native encryption) on all volumes hosting Platform data, including PostgreSQL data, Redis data, backups, and secrets. See `docs/ENCRYPTION_AT_REST.md` for detailed guidance. |
| **Encryption Key Management** | Storing, backing up, and rotating volume encryption keys separately from encrypted data |
| **Physical Security** | Restricting physical access to hardware running the Platform |
| **Network Security** | Configuring firewalls, VPN access, and restricting management ports |
| **Backup Encryption** | Ensuring backups are stored on encrypted media |
| **Operating System Maintenance** | Applying security patches to the host operating system and Docker runtime |

**5.4 User Access Management.** The Controller is responsible for:
- (a) Provisioning and deprovisioning user accounts in accordance with the Controller's access control policies;
- (b) Enforcing MFA enrollment for all users with elevated privileges (Admin, Security Officer, Super Admin roles);
- (c) Reviewing user access permissions periodically;
- (d) Promptly disabling accounts upon employee separation.

**5.5 Compliance Documentation.** The Controller shall maintain records of processing activities as required by Applicable Data Protection Law and shall cooperate with the Processor in providing compliance documentation upon reasonable request.

---

## 6. SECURITY MEASURES

The Processor has implemented the following technical and organizational security measures in the Platform. These measures are documented in detail in the Platform's security documentation (`docs/LEGAL_COMPLIANCE.md`, `docs/SECURITY_ARCHITECTURE.md`, `docs/ENCRYPTION_AT_REST.md`).

### 6.1 Encryption

| Control | Implementation |
|---------|---------------|
| **MFA Secret Encryption** | Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) for TOTP secrets stored in Redis |
| **Sensitive Field Encryption** | AES-256-GCM with PBKDF2-derived keys (100,000 iterations) for sensitive Redis fields |
| **Password Storage** | bcrypt with 12 rounds (one-way hash; not reversible) |
| **Data in Transit** | TLS termination via Traefik reverse proxy with Let's Encrypt certificates; HTTP-to-HTTPS redirect; HSTS headers |
| **Volume Encryption** | Customer responsibility: LUKS, BitLocker, FileVault, or NAS-native encryption on all data volumes |
| **Federation** | AES-256-GCM session keys with RSA-4096 identity keys for cross-instance communication |

### 6.2 Access Control

| Control | Implementation |
|---------|---------------|
| **Role-Based Access Control (RBAC)** | Five-tier role system: Viewer, Operator, Admin, Security Officer, Super Admin. 24 granular permissions across 6 categories. Permission enforcement on all 140+ API endpoints. |
| **Multi-Factor Authentication (MFA)** | RFC 6238 TOTP with QR provisioning, 10 one-time backup codes, replay-safe verification. Required for Admin, Security Officer, and Super Admin roles. |
| **Session Management** | Configurable session duration (default 8 hours), HIPAA-compliant automatic logoff, idle timeouts, session invalidation on user deactivation |
| **Account Lockout** | 5 failed attempts triggers 15-minute lockout; password strength validation (12+ characters, mixed complexity) |
| **API Authentication** | Dual authentication: API Key (SHA-256 hashed storage) and JWT Bearer Token (HS256 signed, configurable expiration) |

### 6.3 Audit and Logging

| Control | Implementation |
|---------|---------------|
| **Cryptographic Audit Chain** | SHA-256 hash-linked log entries; each entry contains the hash of the previous entry, creating a tamper-evident chain. Chain integrity verifiable via API endpoint. |
| **Event Coverage** | 47 event types tracked across authentication, task lifecycle, external requests, agent behavior, security alerts, capability enforcement, approvals, tool operations, and system events |
| **Monotonic Sequencing** | Each chain entry has a monotonically increasing sequence number; gaps are detectable |
| **Compliance Export** | `export_chain_for_compliance()` packages audit entries with verification metadata for auditor consumption |
| **Request Tracing** | Unique UUID assigned to every HTTP request for end-to-end correlation |

### 6.4 Multi-Tenancy and Data Isolation

| Control | Implementation |
|---------|---------------|
| **Tenant Isolation** | Organization-level data isolation with tenant type classification (real_estate, law_firm, insurance, healthcare, small_business, personal, general) |
| **Client-Matter Hierarchy** | Data organized within tenants by client matter with lifecycle management (active, closed, hold) |
| **Redis Key Namespacing** | All data operations scoped via `tenant:{id}:{key}` prefixed keys |
| **Litigation Holds** | Individual matters can be placed on hold, preventing closure or data deletion; hold release requires Security Officer or Super Admin authorization |
| **Data Classification** | Four-tier system: Public, Internal, Confidential, Restricted. Law firm tenants default to Confidential. |

### 6.5 Network Security

| Control | Implementation |
|---------|---------------|
| **Docker Network Segmentation** | Five isolated networks: frontend (public-facing), backend (application), data (internal only), AI (internal only), monitoring (internal only) |
| **Internal Network Enforcement** | Data, AI, and monitoring networks configured as `internal: true` with no external routing |
| **Rate Limiting** | Token bucket algorithm (300 requests/minute, burst 60) with per-tenant rate limiting (600/minute default, configurable) |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, server header stripped |
| **Egress Filtering** | All outbound API calls filtered through domain whitelist |

### 6.6 Monitoring and Alerting

| Control | Implementation |
|---------|---------------|
| **Metrics Collection** | Prometheus metrics for all platform components |
| **Alerting** | Grafana alerting with rules for: HighErrorRate, HighLatency, AuthFailureSpike, AuditChainBroken, ServiceDown |
| **Anomaly Detection** | Six anomaly types monitored: rate spikes, new resources, new actions, unusual timing, enumeration patterns, error spikes |
| **Automated Threat Response** | Critical threats trigger automatic agent quarantine, key revocation, and rate limiting escalation |

---

## 7. DATA BREACH PROCEDURE

### 7.1 Detection and Assessment

Upon detection of a potential Security Incident, the following procedure shall be initiated:

**(a) Initial Detection (T+0).** The Platform's monitoring systems (Prometheus alerting, anomaly detection, audit chain integrity verification) detect or a user reports a potential Security Incident.

**(b) 72-Hour Assessment Window (T+0 to T+72h).** The Controller, using the Platform's breach assessment engine, shall:

| Step | Action | Platform Support |
|------|--------|-----------------|
| 1 | **Classify Severity** | Breach severity classification: Critical, High, Medium, Low |
| 2 | **Identify Scope** | Affected tenant tracking, affected records count, data types exposed |
| 3 | **Assess Containment** | Containment status progression: investigating, contained, remediated |
| 4 | **Determine Notification** | Automated notification requirement determination based on exposed data types |
| 5 | **Calculate Deadlines** | State-law-specific notification deadlines (30-60 days from determination) |

### 7.2 Notification Requirements

The Platform automatically determines notification requirements based on exposed data types:

| Data Type Exposed | Notification Required | Default Deadline |
|-------------------|----------------------|-----------------|
| Social Security Numbers | Yes | 30 days |
| Financial Account Data | Yes | 60 days |
| Personally Identifiable Information | Yes | 60 days |
| Attorney-Client Privileged Material | Yes | 30 days |
| Medical / Health Information | Yes | 60 days |

### 7.3 Notification Workflow

**(a) Notification Recipients.** The Platform tracks notifications to four recipient categories:
- Regulatory authorities (state attorneys general, HHS where applicable);
- Affected individuals (Data Subjects);
- Affected tenants (client organizations);
- Law enforcement (where required or advisable).

**(b) Notification Tracking.** Each notification record includes: recipient identification, notification method, send status, acknowledgment tracking, and timestamp logging.

**(c) Overdue Detection.** The Platform identifies assessments that have passed their notification deadline with pending notifications, enabling the Controller to prioritize overdue obligations.

### 7.4 Processor Notification Obligations

For Security Incidents arising from vulnerabilities in the Platform software:

| Severity | Processor Response Time | Action |
|----------|------------------------|--------|
| Critical | 24 hours | Notification, emergency patch, incident report |
| High | 7 days | Notification, scheduled patch, incident report |
| Medium | 30 days | Notification, next release patch |
| Low | Next release | Included in release notes |

### 7.5 Post-Incident Review

Following resolution of any Security Incident, the Parties shall cooperate in:
- (a) Conducting a root cause analysis;
- (b) Documenting lessons learned;
- (c) Implementing preventive measures;
- (d) Updating security documentation as appropriate.

All breach-related activities shall be recorded in the Platform's cryptographic audit chain to maintain a tamper-evident record for regulatory evidence.

---

## 8. INTERNATIONAL DATA TRANSFERS

**8.1 Self-Hosted Architecture.** Under the standard Self-Hosted Deployment model, no Personal Data is transferred outside the Controller's infrastructure. All data processing, including AI inference, occurs locally within the Controller's network.

**8.2 No Cross-Border Transfers by Processor.** The Processor does not receive, store, or process Personal Data on its own systems in the ordinary course of providing the Platform. Accordingly, no cross-border data transfer mechanisms (Standard Contractual Clauses, Binding Corporate Rules, adequacy decisions) are required for the Processor's provision of the Platform.

**8.3 Controller Responsibility.** If the Controller operates in multiple jurisdictions or transfers Personal Data across borders within its own infrastructure, the Controller is solely responsible for ensuring that such transfers comply with Applicable Data Protection Law.

**8.4 Support Engagements.** If the Controller authorizes the Processor to remotely access the deployment for support purposes, and such access would constitute a cross-border transfer under Applicable Data Protection Law, the Parties shall execute appropriate transfer mechanisms prior to such access.

---

## 9. TERM AND TERMINATION

**9.1 Term.** This DPA shall commence on the Effective Date and shall remain in effect for the duration of the Service Agreement. The obligations of the Processor with respect to Personal Data shall survive termination to the extent required by Applicable Data Protection Law.

**9.2 Effect of Termination.** Upon termination or expiration of the Service Agreement:

**(a) Data Export.** The Controller may export all data from the Platform using the Platform's API endpoints and compliance export functionality at any time prior to or following termination. The Processor shall provide reasonable assistance with data export upon request.

**(b) Data Retention by Controller.** Because the Platform operates on the Controller's infrastructure, the Controller retains all data following termination. The Controller is responsible for securely deleting data in accordance with its own retention policies and Applicable Data Protection Law.

**(c) No Processor Data Retention.** The Processor does not retain any Personal Data following termination, as no Personal Data is transmitted to the Processor's systems in the ordinary course of providing the Platform.

**(d) License Termination.** Upon termination of the Service Agreement, the Controller's license to use the Platform software shall terminate in accordance with the terms of the Service Agreement. The Controller shall cease using the Platform and delete the Platform software unless otherwise agreed.

**(e) Survival.** Sections 4.6 (Data Breach Notification), 4.8 (Return and Deletion of Data), 6 (Security Measures, to the extent applicable to any retained data), and 10 (Liability) shall survive termination of this DPA.

---

## 10. LIABILITY

**10.1 Limitation.** Each Party's liability under this DPA shall be subject to the limitations and exclusions of liability set forth in the Service Agreement.

**10.2 Shared Responsibility.** The Parties acknowledge the shared responsibility model described in Section 5.3. The Processor shall not be liable for Security Incidents arising from the Controller's failure to fulfill its obligations under Section 5, including but not limited to failure to enable volume encryption, failure to apply operating system security patches, or failure to properly manage user access.

---

## 11. AUDIT RIGHTS

**11.1 Controller Audit Rights.** The Controller shall have the right to audit the Processor's compliance with this DPA. The Processor shall make available to the Controller all information necessary to demonstrate compliance with the obligations set forth in this DPA.

**11.2 Platform Self-Audit.** The Platform includes built-in compliance auditing capabilities:
- (a) SOC 2 control mapping with evidence collection framework (`core/compliance.py`);
- (b) Cryptographic audit chain with on-demand integrity verification;
- (c) Compliance report generation with per-control assessment details;
- (d) Data sovereignty score calculation.

**11.3 Third-Party Audits.** Upon reasonable request and subject to reasonable advance notice, the Controller may engage a qualified independent third-party auditor to conduct an audit of the Processor's compliance with this DPA. Such audits shall be conducted during normal business hours, no more than once per twelve-month period, and at the Controller's expense.

---

## 12. GOVERNING LAW AND DISPUTE RESOLUTION

**12.1 Governing Law.** This DPA shall be governed by and construed in accordance with the laws of [JURISDICTION], without regard to conflict of law principles.

**12.2 Dispute Resolution.** Any dispute arising out of or in connection with this DPA shall be resolved in accordance with the dispute resolution provisions of the Service Agreement.

**12.3 Regulatory Compliance.** Notwithstanding the foregoing, nothing in this DPA shall limit either Party's obligations under Applicable Data Protection Law, and to the extent Applicable Data Protection Law imposes stricter requirements than those set forth in this DPA, Applicable Data Protection Law shall prevail.

---

## 13. MISCELLANEOUS

**13.1 Entire Agreement.** This DPA, together with the Service Agreement, constitutes the entire agreement between the Parties with respect to the subject matter hereof and supersedes all prior agreements, understandings, and representations.

**13.2 Amendments.** This DPA may not be amended except by a written instrument signed by both Parties.

**13.3 Severability.** If any provision of this DPA is held to be invalid or unenforceable, the remaining provisions shall remain in full force and effect.

**13.4 Notices.** All notices under this DPA shall be in writing and delivered to the addresses set forth above or to such other address as a Party may designate in writing.

**13.5 Order of Precedence.** In the event of a conflict between this DPA and the Service Agreement, this DPA shall prevail with respect to the processing and protection of Personal Data.

---

## SIGNATURES

**DATA CONTROLLER:**

Name: ___________________________________

Title: ___________________________________

Organization: [CUSTOMER NAME]

Date: ___________________________________

Signature: ___________________________________

**DATA PROCESSOR:**

Name: ___________________________________

Title: ___________________________________

Organization: Quietfire AI (dba TelsonBase)

Date: ___________________________________

Signature: ___________________________________

---

## ANNEX A: DESCRIPTION OF PROCESSING

| Element | Detail |
|---------|--------|
| **Subject Matter** | Provision of self-hosted, zero-trust AI agent security platform for legal and real estate operations |
| **Duration** | For the term of the Service Agreement |
| **Nature of Processing** | Storage, indexing, audit logging, compliance tracking, access control enforcement, AI agent orchestration |
| **Purpose of Processing** | To enable the Controller to manage legal matters, documents, compliance obligations, and AI agent workflows within a secure, auditable environment |
| **Categories of Data Subjects** | Employees and staff, clients, opposing parties, witnesses, third-party contacts |
| **Types of Personal Data** | Identity data, contact data, case and matter data, financial data, protected health information (where applicable), authentication data, behavioral data (activity logs) |
| **Sensitive Data** | Attorney-client privileged communications, protected health information, financial records, government identification numbers |

## ANNEX B: TECHNICAL AND ORGANIZATIONAL MEASURES

Refer to Section 6 of this DPA and the following Platform documentation:

| Document | Location | Coverage |
|----------|----------|----------|
| Legal Compliance Profile | `docs/LEGAL_COMPLIANCE.md` | Full regulatory mapping across SOC 2, ABA Rules, FRCP, state privacy laws |
| Encryption at Rest Guide | `docs/ENCRYPTION_AT_REST.md` | Volume encryption guidance, application-level encryption details, shared responsibility model |
| Security Architecture | `docs/SECURITY_ARCHITECTURE.md` | Nine-layer security architecture overview |
| Incident Response Plan | `docs/INCIDENT_RESPONSE.md` | Severity classification, response procedures, communication templates |
| Backup and Recovery | `docs/BACKUP_RECOVERY.md` | RPO/RTO targets, backup procedures, restoration testing |
| Secrets Management | `docs/SECRETS_MANAGEMENT.md` | Key generation, rotation, and storage procedures |
| Disaster Recovery | `docs/DISASTER_RECOVERY.md` | Recovery procedures, business continuity planning |

## ANNEX C: LIST OF SUB-PROCESSORS

Under the standard Self-Hosted Deployment model, the Processor does not engage Sub-processors for the processing of Personal Data. All data processing occurs on the Controller's infrastructure.

| Sub-processor | Purpose | Location | Data Processed |
|--------------|---------|----------|---------------|
| *None* | *N/A -- Self-Hosted Deployment* | *N/A* | *N/A* |

If this changes, the Processor shall notify the Controller in accordance with Section 4.4(c).

---

*This Data Processing Agreement is a template provided for informational purposes. It should be reviewed, customized, and approved by qualified legal counsel before execution. TelsonBase makes no representation that this template satisfies all legal requirements applicable to any particular Controller's circumstances.*
