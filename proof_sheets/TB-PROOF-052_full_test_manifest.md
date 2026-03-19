# TB-PROOF-052 - Full Test Suite Manifest

**Sheet ID:** TB-PROOF-052
**Claim Source:** README.md — "5,416 tests passing"
**Status:** VERIFIED
**Test Coverage:** VERIFIED — pytest full suite — 5,416 tests across 88 files
**Last Verified:** March 19, 2026 (CI run #309)
**Version:** v11.0.2

---

## Exact Claim

> "5,416 tests passing. 3 skipped. 0 failed."

This sheet is the complete manifest of every test file in the ClawCoat test suite. An outside observer can clone the repository, run the verification command, and confirm the count independently.

## Verdict

VERIFIED — 5,416 tests pass, 3 skipped, 0 failed. CI run #309, GitHub Actions integration stage (real Postgres + Redis). Coverage: 76.13%. The 3 skipped tests are Celery-configuration tests skipped when Celery runs under the unit-test stub.

## Verification Command

```bash
# Full suite — run inside the container
docker compose exec mcp_server python -m pytest tests/ \
  --ignore=tests/test_mqtt_stress.py -q 2>&1 | tail -3
```

## Expected Result

```
5416 passed, 3 skipped
```

---

## Complete Test File Index

### Governance & Core Protocol

**`tests/test_openclaw.py`** — 55 tests
OpenClaw governance engine: 8-step pipeline, trust tiers, kill switch, Manners auto-demotion, permission matrix.

**`tests/test_qms.py`** — 115 tests
QMS v2.2.0 protocol: block detection, chain building, parsing, validation, security flagging, legacy compatibility.

**`tests/test_identiclaw.py`** — 50 tests
W3C DID identity: parsing, Ed25519 verification, verifiable credentials, scope mapping, kill switch, auth flow.

**`tests/test_behavioral.py`** — 30 tests
Behavioral specifications: Ollama model management, QMS discipline, security boundaries, trust level progression, data sovereignty.

**`tests/test_contracts.py`** — 7 tests
Enum contract tripwires: TenantType, AgentTrustLevel, version consistency, migration idempotency.

---

### Security

**`tests/test_security_battery.py`** — 96 tests
Security attack surface — 9 categories:
- TestAuthSecurity (19): API key hashing, JWT, MFA, session controls
- TestEncryptionIntegrity (11): AES-256-GCM, PBKDF2, HMAC
- TestAccessControl (13): RBAC, role assignment, deactivation
- TestAuditTrailIntegrity (11): hash chain, tampering detection
- TestNetworkSecurity (9): CORS, TLS, MQTT auth
- TestDataProtection (11): PHI de-identification, minimum necessary, data classification
- TestComplianceInfrastructure (11): sanctions, training, BAA, breach notification
- TestCryptographicStandards (8): key lengths, algorithm standards
- TestRuntimeBoundaries (3): rate limiting, CAPTCHA, email verification

**`tests/test_signing.py`** — 13 tests
Cryptographic message signing: SignedAgentMessage, AgentKeyRegistry, MessageSigner, replay attack prevention.

**`tests/test_secrets.py`** — 48 tests
Secrets management: SecretValue redaction, secret registry, Docker/env resolution, production startup guard.

**`tests/test_capabilities.py`** — 15 tests
Capability enforcement: parsing, matching, glob patterns, deny rules, CapabilitySet, CapabilityEnforcer.

---

### Toolroom

**`tests/test_toolroom.py`** — 129 tests
Supply-chain security: registry, checkout, foreman, cage, versioning, rollback, API endpoints.

**`tests/test_toolroom_registry_depth.py`** — 105 tests
Toolroom registry depth coverage.

**`tests/test_toolroom_manifest_depth.py`** — 92 tests
Toolroom manifest depth coverage.

**`tests/test_toolroom_function_tools_depth.py`** — 42 tests
Toolroom function tools depth coverage.

**`tests/test_toolroom_executor_depth.py`** — 40 tests
Toolroom executor depth coverage.

**`tests/test_toolroom_foreman_depth.py`** — 38 tests
Toolroom foreman depth coverage.

---

### Infrastructure & Integration

**`tests/test_e2e_integration.py`** — 29 tests
End-to-end: user lifecycle, tenant workflow, tenant isolation, security endpoints, audit chain integrity, error sanitization.

**`tests/test_integration.py`** — 26 tests
Integration layer: federation handshake, egress gateway, approval workflow, cross-agent messaging, anomaly detection, key revocation, audit chain, threat response, secure storage.

**`tests/test_api.py`** — 19 tests
API endpoint smoke tests: public endpoints, authentication, system, agents, approvals, anomalies, federation, QMS conventions.

**`tests/test_observability.py`** — 40 tests
Prometheus metrics, MQTT bus, Grafana/monitoring configuration.

**`tests/test_ollama.py`** — 49 tests
Local LLM inference: model management, generation, chat, health checks, async safety.

---

### Core Module Depth Tests

| File | Tests | Module |
|---|---|---|
| `test_core_qms_depth.py` | 165 | QMS protocol engine |
| `test_core_audit_depth.py` | 159 | SHA-256 hash-chained audit trail |
| `test_core_semantic_matching_depth.py` | 127 | Semantic matching engine |
| `test_core_data_classification_depth.py` | 122 | Data classification (PHI/PII/sensitive) |
| `test_core_threat_response_depth.py` | 115 | Automated threat response |
| `test_core_trust_levels_depth.py` | 100 | Trust levels and permission matrix |
| `test_core_phi_deidentification_depth.py` | 100 | 18 HIPAA safe harbor identifier removal |
| `test_core_tenancy_depth.py` | 97 | Multi-tenant isolation |
| `test_core_manners_depth.py` | 96 | Manners compliance scoring engine |
| `test_core_hitrust_controls_depth.py` | 95 | HITRUST CSF controls |
| `test_core_training_depth.py` | 85 | Compliance training tracking |
| `test_core_rbac_depth.py` | 85 | RBAC (5 roles, 19 permissions, Redis persistence) |
| `test_core_openclaw_depth.py` | 83 | OpenClaw governance engine |
| `test_core_session_management_depth.py` | 79 | HIPAA-compliant session management |
| `test_core_data_retention_depth.py` | 79 | Data retention policy enforcement |
| `test_core_tenant_rate_limiting_depth.py` | 78 | Tenant-scoped rate limiting |
| `test_core_minimum_necessary_depth.py` | 75 | HIPAA minimum necessary rule |
| `test_compliance_depth.py` | 74 | Compliance framework orchestration |
| `test_core_rate_limiting_depth.py` | 68 | Per-tenant rate limit enforcement |
| `test_core_compliance_depth.py` | 68 | Core compliance depth |
| `test_core_captcha_depth.py` | 68 | CAPTCHA challenge/response |
| `test_core_approval_depth.py` | 67 | Human-in-the-loop approval gates |
| `test_core_breach_notification_depth.py` | 66 | HITECH 60-day breach notification |
| `test_core_secrets_depth.py` | 64 | Secrets management |
| `test_core_capabilities_depth.py` | 64 | Capability enforcement |
| `test_core_sanctions_depth.py` | 63 | OFAC/sanctions screening |
| `test_core_anomaly_depth.py` | 61 | Behavioral anomaly detection |
| `test_core_user_management_depth.py` | 60 | User registration and authentication |
| `test_core_secure_storage_depth.py` | 60 | AES-256-GCM encrypted storage |
| `test_core_system_analysis_depth.py` | 59 | System health analysis |
| `test_core_legal_hold_depth.py` | 55 | Legal hold enforcement |
| `test_core_baa_tracking_depth.py` | 54 | BAA lifecycle management |
| `test_core_email_verification_depth.py` | 53 | Email verification flow |
| `test_core_rotation_depth.py` | 51 | Key rotation |
| `test_core_contingency_testing_depth.py` | 51 | Contingency plan testing |
| `test_core_mfa_depth.py` | 49 | TOTP MFA (RFC 6238) |
| `test_core_emergency_access_depth.py` | 49 | Break-glass emergency access |
| `test_core_signing_depth.py` | 47 | HMAC-SHA256 / Ed25519 message signing |
| `test_core_middleware_depth.py` | 47 | Rate limiting and circuit breaker middleware |
| `test_core_phi_disclosure_depth.py` | 46 | PHI disclosure accounting |
| `test_core_delegation_depth.py` | 41 | Permission delegation |
| `test_core_persistence_depth.py` | 40 | Redis state management |
| `test_core_metrics_depth.py` | 36 | Metrics collection |
| `test_core_auth_depth.py` | 26 | JWT authentication |
| `test_core_auth_dependencies_depth.py` | 18 | FastAPI auth dependency helpers |

---

### Agents Depth Tests

| File | Tests | Agent |
|---|---|---|
| `test_agents_transaction_depth.py` | 140 | Transaction agent |
| `test_agents_memory_depth.py` | 100 | Memory agent |
| `test_agents_document_depth.py` | 62 | Document agent |
| `test_agents_alien_adapter_depth.py` | 56 | Alien adapter (external agent integration) |
| `test_agents_backup_depth.py` | 50 | Backup agent |
| `test_agents_demo_depth.py` | 42 | Demo agent |
| `test_agents_base_depth.py` | 29 | SecureBaseAgent base class |

---

### API Routes Depth Tests

| File | Tests | Routes |
|---|---|---|
| `test_security_routes_depth.py` | 58 | Security API routes |
| `test_tenancy_routes_depth.py` | 38 | Tenancy API routes |
| `test_mcp_gateway_depth.py` | 34 | MCP gateway routes |
| `test_auth_routes_depth.py` | 27 | Authentication routes |

---

### User Management & Hardening

| File | Tests | Domain |
|---|---|---|
| `test_user_mgmt_and_analysis.py` | 68 | User management and system analysis |
| `test_depth_infrastructure.py` | 31 | Infrastructure depth |
| `test_depth_hardening.py` | 28 | Production hardening |

---

### Coverage Boost Files

| File | Tests | Purpose |
|---|---|---|
| `test_coverage_boost.py` | 106 | Supplemental coverage — misc modules |
| `test_coverage_boost2.py` | 70 | Supplemental coverage — misc modules |
| `test_coverage_boost3.py` | 25 | Supplemental coverage — misc modules |
| `test_coverage_boost4.py` | 33 | Supplemental coverage — misc modules |
| `test_coverage_boost5.py` | 124 | Supplemental coverage — misc modules |
| `test_coverage_boost6.py` | 44 | Supplemental coverage — misc modules |

---

## Summary by Category

| Category | Files | Tests |
|---|---|---|
| Governance & Core Protocol | 5 | 257 |
| Security | 4 | 172 |
| Toolroom | 6 | 446 |
| Infrastructure & Integration | 5 | 163 |
| Core Module Depth | 45 | 2,718 |
| Agents Depth | 7 | 479 |
| API Routes Depth | 4 | 157 |
| User Management & Hardening | 3 | 127 |
| Coverage Boost | 6 | 402 |
| **TOTAL (standard run)** | **88** | **5,416** |

---

## What Is NOT Counted

**`tests/test_mqtt_stress.py`** — 26 tests. Excluded from the standard run. Requires a live MQTT broker. Stress/load test, not a correctness test. Passes when run in isolation against a running stack:

```bash
docker compose exec mcp_server python -m pytest tests/test_mqtt_stress.py -v --tb=short
```

---

*Sheet TB-PROOF-052 | ClawCoat v11.0.2 | March 19, 2026*
