# TB-PROOF-001: Test Suite Count

**Sheet ID:** TB-PROOF-001
**Claim Source:** clawcoat.com - Hero Section / README.md
**Status:** VERIFIED
**Test Coverage:** VERIFIED — pytest full suite (unit + integration) — 5,416 tests
**Last Verified:** March 19, 2026 (CI run #309)
**Version:** v11.0.2

---

## Exact Claim

> "5,416 tests passing. 3 skipped. 0 failed."

## Verdict

VERIFIED — **5,416 passing, 3 skipped, 0 failed**. Verified via CI run #309 (GitHub Actions, real Postgres + Redis integration stage). Coverage: 76.13% (gate: 63%). Includes original governance and security tests plus deep coverage of every core module, agent layer, toolroom, compliance infrastructure, and API routes.

## Evidence

### Test Suite Summary (88 files)

| File | Tests | Domain |
|---|---|---|
| `test_core_qms_depth.py` | 165 | QMS protocol depth coverage |
| `test_core_audit_depth.py` | 159 | Audit chain depth coverage |
| `test_agents_transaction_depth.py` | 140 | Transaction agent depth |
| `test_toolroom.py` | 129 | Toolroom supply-chain security |
| `test_core_semantic_matching_depth.py` | 127 | Semantic matching depth |
| `test_coverage_boost5.py` | 124 | Coverage boost (misc modules) |
| `test_core_data_classification_depth.py` | 122 | Data classification depth |
| `test_qms.py` | 115 | QMS v2.2.0 protocol specification |
| `test_core_threat_response_depth.py` | 115 | Threat response depth |
| `test_coverage_boost.py` | 106 | Coverage boost (misc modules) |
| `test_toolroom_registry_depth.py` | 105 | Toolroom registry depth |
| `test_core_trust_levels_depth.py` | 100 | Trust levels depth |
| `test_core_phi_deidentification_depth.py` | 100 | PHI de-identification (18 safe harbor identifiers) |
| `test_agents_memory_depth.py` | 100 | Memory agent depth |
| `test_core_tenancy_depth.py` | 97 | Multi-tenant isolation depth |
| `test_security_battery.py` | 96 | Security attack surface (9 categories) |
| `test_core_manners_depth.py` | 96 | Manners engine depth |
| `test_core_hitrust_controls_depth.py` | 95 | HITRUST CSF controls depth |
| `test_toolroom_manifest_depth.py` | 92 | Toolroom manifest depth |
| `test_core_training_depth.py` | 85 | Compliance training depth |
| `test_core_rbac_depth.py` | 85 | RBAC depth coverage |
| `test_core_openclaw_depth.py` | 83 | OpenClaw governance depth |
| `test_core_session_management_depth.py` | 79 | Session management depth |
| `test_core_data_retention_depth.py` | 79 | Data retention depth |
| `test_core_tenant_rate_limiting_depth.py` | 78 | Tenant rate limiting depth |
| `test_core_minimum_necessary_depth.py` | 75 | HIPAA minimum necessary depth |
| `test_compliance_depth.py` | 74 | Compliance framework depth |
| `test_coverage_boost2.py` | 70 | Coverage boost (misc modules) |
| `test_user_mgmt_and_analysis.py` | 68 | User management and system analysis |
| `test_core_rate_limiting_depth.py` | 68 | Rate limiting depth |
| `test_core_compliance_depth.py` | 68 | Core compliance depth |
| `test_core_captcha_depth.py` | 68 | CAPTCHA depth |
| `test_core_approval_depth.py` | 67 | Approval gates depth |
| `test_core_breach_notification_depth.py` | 66 | HITECH breach notification depth |
| `test_core_secrets_depth.py` | 64 | Secrets management depth |
| `test_core_capabilities_depth.py` | 64 | Capability enforcement depth |
| `test_core_sanctions_depth.py` | 63 | Sanctions screening depth |
| `test_agents_document_depth.py` | 62 | Document agent depth |
| `test_core_anomaly_depth.py` | 61 | Behavioral anomaly detection depth |
| `test_core_user_management_depth.py` | 60 | User management depth |
| `test_core_secure_storage_depth.py` | 60 | AES-256-GCM secure storage depth |
| `test_core_system_analysis_depth.py` | 59 | System analysis depth |
| `test_security_routes_depth.py` | 58 | Security API routes depth |
| `test_agents_alien_adapter_depth.py` | 56 | Alien adapter depth |
| `test_openclaw.py` | 55 | OpenClaw governance pipeline |
| `test_core_legal_hold_depth.py` | 55 | Legal hold enforcement depth |
| `test_core_baa_tracking_depth.py` | 54 | BAA lifecycle depth |
| `test_core_email_verification_depth.py` | 53 | Email verification depth |
| `test_core_rotation_depth.py` | 51 | Key rotation depth |
| `test_core_contingency_testing_depth.py` | 51 | Contingency testing depth |
| `test_identiclaw.py` | 50 | DID identity, Ed25519, verifiable credentials |
| `test_agents_backup_depth.py` | 50 | Backup agent depth |
| `test_ollama.py` | 49 | Local LLM inference integration |
| `test_core_mfa_depth.py` | 49 | TOTP MFA depth |
| `test_core_emergency_access_depth.py` | 49 | Emergency access depth |
| `test_secrets.py` | 48 | Secrets management |
| `test_core_signing_depth.py` | 47 | Cryptographic signing depth |
| `test_core_middleware_depth.py` | 47 | Middleware depth |
| `test_core_phi_disclosure_depth.py` | 46 | PHI disclosure accounting depth |
| `test_coverage_boost6.py` | 44 | Coverage boost (misc modules) |
| `test_toolroom_function_tools_depth.py` | 42 | Toolroom function tools depth |
| `test_agents_demo_depth.py` | 42 | Demo agent depth |
| `test_core_delegation_depth.py` | 41 | Permission delegation depth |
| `test_toolroom_executor_depth.py` | 40 | Toolroom executor depth |
| `test_observability.py` | 40 | Metrics, Prometheus, audit log |
| `test_core_persistence_depth.py` | 40 | Redis persistence depth |
| `test_toolroom_foreman_depth.py` | 38 | Toolroom foreman depth |
| `test_tenancy_routes_depth.py` | 38 | Tenancy API routes depth |
| `test_core_metrics_depth.py` | 36 | Metrics depth |
| `test_mcp_gateway_depth.py` | 34 | MCP gateway depth |
| `test_coverage_boost4.py` | 33 | Coverage boost (misc modules) |
| `test_depth_infrastructure.py` | 31 | Infrastructure depth |
| `test_behavioral.py` | 30 | Trust progression behavioral specs |
| `test_e2e_integration.py` | 29 | End-to-end: auth, tenant, audit, error sanitization |
| `test_agents_base_depth.py` | 29 | Agent base class depth |
| `test_depth_hardening.py` | 28 | Hardening depth |
| `test_auth_routes_depth.py` | 27 | Auth API routes depth |
| `test_integration.py` | 26 | Integration layer |
| `test_core_auth_depth.py` | 26 | Auth module depth |
| `test_coverage_boost3.py` | 25 | Coverage boost (misc modules) |
| `test_api.py` | 19 | API endpoint smoke tests |
| `test_core_auth_dependencies_depth.py` | 18 | Auth dependencies depth |
| `test_capabilities.py` | 15 | Capability profiles and declarations |
| `test_signing.py` | 13 | RSA/Ed25519 payload signing |
| `test_contracts.py` | 7 | Enum contract tripwires + version consistency |
| **TOTAL (standard run)** | **5,416** | **Full governance platform** |

### Not Counted: `test_mqtt_stress.py` (26 tests)
Excluded from the standard run — requires a live MQTT broker. Stress/load test, not a correctness test. Passes when run against a running stack.

### Version History (test count milestones)
| Version | Tests Passing | Notable Addition |
|---|---|---|
| 5.1.0CC | 509 | Secrets management |
| 6.1.0CC | 503 | CVE remediation |
| 7.0.0CC | 618 | Full hardening roadmap |
| 8.0.2 | 727 | Stability fixes, multi-stage Dockerfile |
| 9.0.0B | 720 | OpenClaw + AGENT 5th tier |
| 11.0.1 | 854 | OpenClaw depth, integration tests |
| **11.0.2** | **5,416** | **Deep coverage: all core modules, agents, toolroom, compliance, API routes** |

## Verification Command

```bash
# Run inside the container
docker compose exec mcp_server python -m pytest tests/ \
  --ignore=tests/test_mqtt_stress.py -q 2>&1 | tail -3
```

## Expected Result

```
5416 passed, 3 skipped
```

---

*Sheet TB-PROOF-001 | ClawCoat v11.0.2 | March 19, 2026*
