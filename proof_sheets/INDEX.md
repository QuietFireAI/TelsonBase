# ClawCoat Proof Sheets

**Every claim is backed by evidence.**

Every claim made on [clawcoat.com](https://clawcoat.com) has a corresponding evidence sheet in this directory. Each sheet documents the exact claim, provides the source code files, test files, and verification commands that prove it. No marketing fluff - just traceable evidence.

**Format:** Each sheet follows a standardized format inspired by Safety Data Sheets (SDS). Grab the sheet number, verify the claim, move on.

**Last Verified:** March 8, 2026 | **Version:** v11.0.1 | **Tests Passing:** 746 | **Proof Documents:** 788 (67 class-level + 721 individual)

---

## Sheet Index

### Test Suite and Code Quality
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-001](TB-PROOF-001_tests_passing.md) | 720 Tests Passing | VERIFIED |
| [TB-PROOF-002](TB-PROOF-002_security_tests.md) | 96 Dedicated Security Tests | VERIFIED |
| [TB-PROOF-003](TB-PROOF-003_production_hardening.md) | 22 Production Hardening Items Completed | VERIFIED |

### Compliance and Controls
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-004](TB-PROOF-004_soc2_controls.md) | 51 SOC 2 Controls Mapped to Source Code | VERIFIED |
| [TB-PROOF-005](TB-PROOF-005_hipaa_security_rule.md) | HIPAA Security Rule Full Mapping | VERIFIED |
| [TB-PROOF-006](TB-PROOF-006_hitrust_csf.md) | HITRUST CSF 12 Domains | VERIFIED |
| [TB-PROOF-007](TB-PROOF-007_phi_deidentification.md) | PHI De-identification (18 Safe Harbor Identifiers) | VERIFIED |
| [TB-PROOF-008](TB-PROOF-008_hitech_breach_notification.md) | HITECH Breach Notification (60-Day Tracking) | VERIFIED |

### Cryptography and Encryption
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-009](TB-PROOF-009_audit_chain_sha256.md) | SHA-256 Hash-Chained Audit Trail | VERIFIED |
| [TB-PROOF-010](TB-PROOF-010_aes256_encryption.md) | AES-256-GCM Encryption at Rest | VERIFIED |
| [TB-PROOF-011](TB-PROOF-011_pbkdf2_key_derivation.md) | PBKDF2 Key Derivation (100,000+ Iterations) | VERIFIED |
| [TB-PROOF-012](TB-PROOF-012_tls_hsts.md) | TLS 1.2+ with HSTS Preload | VERIFIED |
| [TB-PROOF-013](TB-PROOF-013_message_signing.md) | Cryptographic Message Signing Between Agents | VERIFIED |

### Authentication and Access Control
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-014](TB-PROOF-014_rbac_endpoints.md) | 150 RBAC-Protected Endpoints | VERIFIED |
| [TB-PROOF-015](TB-PROOF-015_totp_mfa.md) | RFC 6238 TOTP Multi-Factor Authentication | VERIFIED |
| [TB-PROOF-016](TB-PROOF-016_session_management.md) | HIPAA-Compliant Session Management | VERIFIED |
| [TB-PROOF-017](TB-PROOF-017_account_lockout.md) | Account Lockout After 5 Failed Attempts | VERIFIED |

### Agent Governance
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-018](TB-PROOF-018_anthropic_safety_framework.md) | Built on Anthropic's Agent Safety Framework (Manners) | VERIFIED |
| [TB-PROOF-019](TB-PROOF-019_hitl_approval_gates.md) | Human-in-the-Loop Approval Gates | VERIFIED |
| [TB-PROOF-020](TB-PROOF-020_anomaly_detection.md) | Behavioral Anomaly Detection | VERIFIED |
| [TB-PROOF-021](TB-PROOF-021_multi_tenant_isolation.md) | Multi-Tenant Data Isolation | VERIFIED |
| [TB-PROOF-042](TB-PROOF-042_tenant_access_control.md) | Tenant Access Control - allowed_actors Enforcement | VERIFIED |

### Security Testing
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-022](TB-PROOF-022_api_fuzz_testing.md) | 177 API Operations Fuzz-Tested | VERIFIED |
| [TB-PROOF-023](TB-PROOF-023_generated_test_cases.md) | 107,811 Generated Test Cases | VERIFIED |
| [TB-PROOF-024](TB-PROOF-024_zero_server_errors.md) | 0 Server Errors Under Fuzzing | VERIFIED |
| [TB-PROOF-025](TB-PROOF-025_security_test_levels.md) | 5 Automated Security Test Levels | VERIFIED |
| [TB-PROOF-026](TB-PROOF-026_concurrent_requests.md) | 50 Concurrent Requests Handled | VERIFIED |
| [TB-PROOF-027](TB-PROOF-027_static_analysis.md) | 0 High-Severity Findings (Static Analysis) | VERIFIED |

### Data Sovereignty
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-028](TB-PROOF-028_zero_data_leaves.md) | Zero Data Leaves Your Network | VERIFIED |
| [TB-PROOF-029](TB-PROOF-029_local_llm_ollama.md) | Local LLM Inference via Ollama | VERIFIED |
| [TB-PROOF-030](TB-PROOF-030_no_third_party_deps.md) | No Third-Party Data Dependencies | VERIFIED |

### Infrastructure
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-031](TB-PROOF-031_non_root_container.md) | Non-Root Container Execution | VERIFIED |
| [TB-PROOF-032](TB-PROOF-032_self_hosted_services.md) | 10 Self-Hosted Services | VERIFIED |
| [TB-PROOF-033](TB-PROOF-033_disaster_recovery.md) | Disaster Recovery RPO=24hr RTO=15min | VERIFIED |
| [TB-PROOF-034](TB-PROOF-034_documentation_suite.md) | Contract-Ready Documentation Suite | VERIFIED |

### OpenClaw Governance ("Control Your Claw")
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-035](TB-PROOF-035_openclaw_governance.md) | OpenClaw Governance Pipeline | VERIFIED |
| [TB-PROOF-036](TB-PROOF-036_trust_level_matrix.md) | Trust Level Permission Matrix | VERIFIED |
| [TB-PROOF-037](TB-PROOF-037_openclaw_kill_switch.md) | OpenClaw Kill Switch | VERIFIED |
| [TB-PROOF-038](TB-PROOF-038_manners_auto_demotion.md) | Manners Auto-Demotion | VERIFIED |
| [TB-PROOF-039](TB-PROOF-039_earned_trust_model.md) | Earned Trust Model | VERIFIED |

### Integration Guides
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-040](TB-PROOF-040_openclaw_integration_guide.md) | OpenClaw Integration: Start to Finish (under 45 min) | VERIFIED |
| [TB-PROOF-041](TB-PROOF-041_agent_registration.md) | How to Add an Agent - Developer Deep Dive | VERIFIED |

### Security Battery - Test-by-Test Evidence
*One proof sheet per test class. Every claim in the 96-test security battery is traceable to source code and a verification command.*

| Sheet | Claim | Tests | Status |
|---|---|---|---|
| [TB-PROOF-043](TB-PROOF-043_security_auth.md) | Authentication Security - API key hashing, JWT lifecycle, MFA, sessions | 19 | VERIFIED |
| [TB-PROOF-044](TB-PROOF-044_security_encryption.md) | Encryption Integrity - AES-256-GCM, PBKDF2, HMAC correctness | 11 | VERIFIED |
| [TB-PROOF-045](TB-PROOF-045_security_access_control.md) | Access Control - RBAC enforcement, custom grants/denials, deactivation | 13 | VERIFIED |
| [TB-PROOF-046](TB-PROOF-046_security_audit_trail.md) | Audit Trail Integrity - SHA-256 chain, tamper detection, UTC timestamps | 11 | VERIFIED |
| [TB-PROOF-047](TB-PROOF-047_security_network.md) | Network Security - CORS, Redis auth, production mode, session timeouts, MQTT | 9 | VERIFIED |
| [TB-PROOF-048](TB-PROOF-048_security_data_protection.md) | Data Protection & Privacy - PHI de-id (18 identifiers), minimum necessary, legal hold | 11 | VERIFIED |
| [TB-PROOF-049](TB-PROOF-049_security_compliance.md) | Compliance Infrastructure - HITRUST, BAA lifecycle, breach notification, sanctions | 11 | VERIFIED |
| [TB-PROOF-050](TB-PROOF-050_security_cryptography.md) | Cryptographic Standards - algorithm verification, key sizes, RFC 6238 TOTP | 8 | VERIFIED |
| [TB-PROOF-051](TB-PROOF-051_security_runtime_boundaries.md) | Runtime Boundary Enforcement - rate limiter, CAPTCHA expiry, email token expiry | 3 | VERIFIED |

### Full Test Suite Manifest
| Sheet | Claim | Status |
|---|---|---|
| [TB-PROOF-052](TB-PROOF-052_full_test_manifest.md) | Complete 720-Test Suite Manifest - every file, class, and function name | VERIFIED |

### Test Suite Class-Level Evidence
*One proof sheet per test suite. Every test class in each suite is listed with its test count and what it proves.*

| Sheet | Suite | Classes | Tests | Status |
|---|---|---|---|---|
| [TB-PROOF-053](tb-proof-053_qms_suite.md) | Qualified Message Standard (QMS(TM)) | 13 | 115 | VERIFIED |
| [TB-PROOF-054](tb-proof-054_toolroom_suite.md) | Toolroom and Foreman Agent | 28 | 129 | VERIFIED |
| [TB-PROOF-055](tb-proof-055_openclaw_suite.md) | OpenClaw Agent Governance | 9 | 55 | VERIFIED |
| [TB-PROOF-056](tb-proof-056_identiclaw_suite.md) | IdentiClaw Identity and Verification | 12 | 50 | VERIFIED |
| [TB-PROOF-057](tb-proof-057_ollama_suite.md) | Ollama LLM Service | 12 | 49 | VERIFIED |
| [TB-PROOF-058](tb-proof-058_observability_suite.md) | Observability and Metrics | 6 | 40 | VERIFIED |
| [TB-PROOF-059](tb-proof-059_behavioral_suite.md) | Behavioral (GIVEN/WHEN/THEN) | 6 | 30 | VERIFIED |
| [TB-PROOF-060](tb-proof-060_e2e_suite.md) | End-to-End Integration | 6 | 29 | VERIFIED |
| [TB-PROOF-061](tb-proof-061_secrets_suite.md) | Secrets Management | 7 | 48 | VERIFIED |
| [TB-PROOF-062](tb-proof-062_integration_suite.md) | Cross-System Integration | 9 | 26 | VERIFIED |
| [TB-PROOF-063](tb-proof-063_capabilities_suite.md) | Capability Enforcement | 3 | 15 | VERIFIED |
| [TB-PROOF-064](tb-proof-064_signing_suite.md) | Message Signing and Verification | 3 | 13 | VERIFIED |
| [TB-PROOF-065](tb-proof-065_api_suite.md) | REST API Endpoints | 8 | 19 | VERIFIED |
| [TB-PROOF-066](tb-proof-066_contracts_suite.md) | Enum Contracts and Operational Invariants | 4 | 7 | VERIFIED |
| [TB-PROOF-067](tb-proof-067_mqtt_stress_suite.md) | MQTT Bus Load and Stress | 8 | 26 | VERIFIED |

---

## How to Use This Directory

1. Someone questions a claim on the website? Find the sheet number above.
2. Open the sheet. It contains the exact claim, the source files, the test files, and a verification command.
3. Run the verification command. If it passes, the claim holds. If it fails, file a bug.

## Verification

Run all proof verification tests at once:
```bash
docker compose exec mcp_server python -m pytest tests/ -v --tb=short --ignore=tests/test_mqtt_stress.py
```

---

*Generated February 23, 2026 | TelsonBase v11.0.1 | Updated March 8, 2026*
