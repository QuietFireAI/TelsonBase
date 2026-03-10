# TelsonBase — Documentation Index

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

Complete index of all documentation in the repository. Root-level files follow OSS convention. Everything else lives under `docs/` organized by category.

For proof sheet evidence (773 documents): see [`proof_sheets/INDEX.md`](proof_sheets/INDEX.md).

---

## Root — Standard OSS Files

| File | Purpose |
|---|---|
| [README.md](README.md) | Project overview, architecture, quickstart, GIFs, screenshots |
| [CHANGELOG.md](CHANGELOG.md) | Version history (keepachangelog format) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute — branches, PRs, tests |
| [GOVERNANCE.md](GOVERNANCE.md) | Project governance — maintainers, decisions, releases |
| [SUPPORT.md](SUPPORT.md) | Support channels and how to get help |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](SECURITY.md) | Security policy and responsible disclosure |
| [TERMS_OF_USE.md](TERMS_OF_USE.md) | Terms of use and liability |
| [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) | Commercial licensing options |
| [TRADEMARKS.md](TRADEMARKS.md) | TelsonBase and QMS™ trademark policy |
| [AMBASSADORS.md](AMBASSADORS.md) | Ambassador program — roles, how to apply |
| [GLOSSARY.md](GLOSSARY.md) | Terminology reference for the full platform |
| [MANNERS.md](MANNERS.md) | Manners compliance framework — five principles and KPI tables |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Repository layout and directory descriptions |
| [TESTING.md](TESTING.md) | Testing overview — how to run, suite breakdown |
| [USER_GUIDE.md](USER_GUIDE.md) | End-user guide to the admin dashboard and console |
| [CITATION.cff](CITATION.cff) | Machine-readable citation metadata (GitHub auto-generates formatted citation) |
| [NOTICE](NOTICE) | Apache 2.0 attribution and third-party notices |

---

## docs/ — Technical and Operational Documentation

### Getting Started

| File | Purpose |
|---|---|
| [docs/YOUR_FIRST_AGENT.md](docs/YOUR_FIRST_AGENT.md) | Step-by-step: register an agent, observe Manners scoring, earn promotion |
| [docs/DASHBOARD_agent_registration.md](docs/DASHBOARD_agent_registration.md) | Dashboard walkthrough for agent registration |
| [docs/DEMO_WALKTHROUGH_step_by_step.md](docs/DEMO_WALKTHROUGH_step_by_step.md) | Full demo sequence for live presentations |
| [docs/FAQ.md](docs/FAQ.md) | Frequently asked questions |
| [docs/WHATS_NEXT.md](docs/WHATS_NEXT.md) | Post-launch roadmap and planned features |

### Operation

| File | Purpose |
|---|---|
| [docs/Operation Documents/DEVELOPER_GUIDE.md](docs/Operation%20Documents/DEVELOPER_GUIDE.md) | Architecture deep-dive for contributors and integrators |
| [docs/Operation Documents/DEPLOYMENT_GUIDE.md](docs/Operation%20Documents/DEPLOYMENT_GUIDE.md) | Production deployment — DigitalOcean, self-hosted, Docker |
| [docs/Operation Documents/INSTALLATION_GUIDE_WINDOWS.md](docs/Operation%20Documents/INSTALLATION_GUIDE_WINDOWS.md) | Windows local setup with copy-paste commands |
| [docs/Operation Documents/OPENCLAW_INTEGRATION_GUIDE.md](docs/Operation%20Documents/OPENCLAW_INTEGRATION_GUIDE.md) | Integrating OpenClaw agents with TelsonBase governance |
| [docs/Operation Documents/OPENCLAW_OPERATIONS.md](docs/Operation%20Documents/OPENCLAW_OPERATIONS.md) | Day-to-day OpenClaw operations reference |
| [docs/Operation Documents/TROUBLESHOOTING.md](docs/Operation%20Documents/TROUBLESHOOTING.md) | Common issues and resolution steps |
| [docs/Operation Documents/SHARED_RESPONSIBILITY.md](docs/Operation%20Documents/SHARED_RESPONSIBILITY.md) | What TelsonBase handles vs. what the deployer handles |
| [docs/Operation Documents/PRICING_MODEL.md](docs/Operation%20Documents/PRICING_MODEL.md) | Pricing tiers and commercial options |

### System Architecture

| File | Purpose |
|---|---|
| [docs/System Documents/SECURITY_ARCHITECTURE.md](docs/System%20Documents/SECURITY_ARCHITECTURE.md) | Full security architecture — layers, controls, threat model |
| [docs/System Documents/API_REFERENCE.md](docs/System%20Documents/API_REFERENCE.md) | Complete API reference (all 161 endpoints) |
| [docs/System Documents/ENV_CONFIGURATION.md](docs/System%20Documents/ENV_CONFIGURATION.md) | `.env` variables — all settings documented |
| [docs/System Documents/SECRETS_MANAGEMENT.md](docs/System%20Documents/SECRETS_MANAGEMENT.md) | How secrets are generated, stored, and rotated |
| [docs/System Documents/ENCRYPTION_AT_REST.md](docs/System%20Documents/ENCRYPTION_AT_REST.md) | AES-256-GCM encryption implementation and key management |
| [docs/System Documents/HA_ARCHITECTURE.md](docs/System%20Documents/HA_ARCHITECTURE.md) | High-availability deployment architecture |
| [docs/System Documents/PROJECT_OVERVIEW.md](docs/System%20Documents/PROJECT_OVERVIEW.md) | Technical project overview — design decisions and rationale |
| [docs/System Documents/DATA_PROCESSING_AGREEMENT.md](docs/System%20Documents/DATA_PROCESSING_AGREEMENT.md) | DPA template for enterprise deployments |
| [docs/System Documents/SOC2_TYPE_I.md](docs/System%20Documents/SOC2_TYPE_I.md) | SOC 2 Type I control mapping to source code |

### Compliance

| File | Purpose |
|---|---|
| [docs/Compliance Documents/MANNERS_COMPLIANCE.md](docs/Compliance%20Documents/MANNERS_COMPLIANCE.md) | Manners runtime scoring — principles, violation types, API endpoints |
| [docs/Compliance Documents/HEALTHCARE_COMPLIANCE.md](docs/Compliance%20Documents/HEALTHCARE_COMPLIANCE.md) | HIPAA / HITECH / HITRUST control mapping |
| [docs/Compliance Documents/LEGAL_COMPLIANCE.md](docs/Compliance%20Documents/LEGAL_COMPLIANCE.md) | ABA Model Rules / legal industry compliance mapping |
| [docs/Compliance Documents/COMPLIANCE_ROADMAP.md](docs/Compliance%20Documents/COMPLIANCE_ROADMAP.md) | Compliance certification roadmap (SOC 2 Type II, etc.) |
| [docs/Compliance Documents/PENTEST_PREPARATION.md](docs/Compliance%20Documents/PENTEST_PREPARATION.md) | Pre-engagement pentest checklist and scope guidance |

### Security

| File | Purpose |
|---|---|
| [docs/SECURITY_GUIDELINES.md](docs/SECURITY_GUIDELINES.md) | Security hardening guidelines for deployers |
| [docs/AUDIT_TRAIL.md](docs/AUDIT_TRAIL.md) | Cryptographic audit chain — structure, verification, retention |
| [docs/TOOLROOM_TRUST_MATRIX.md](docs/TOOLROOM_TRUST_MATRIX.md) | Tool risk categories and trust tier permission matrix |

### QMS Protocol

| File | Purpose |
|---|---|
| [docs/QMS Documents/QMS_SPECIFICATION.md](docs/QMS%20Documents/QMS_SPECIFICATION.md) | Qualified Message Standard full specification |

### Backup and Recovery

| File | Purpose |
|---|---|
| [docs/Backup and Recovery Documents/BACKUP_RECOVERY.md](docs/Backup%20and%20Recovery%20Documents/BACKUP_RECOVERY.md) | Backup procedures and schedules |
| [docs/Backup and Recovery Documents/DISASTER_RECOVERY.md](docs/Backup%20and%20Recovery%20Documents/DISASTER_RECOVERY.md) | Disaster recovery plan |
| [docs/Backup and Recovery Documents/INCIDENT_RESPONSE.md](docs/Backup%20and%20Recovery%20Documents/INCIDENT_RESPONSE.md) | Security incident response playbook |
| [docs/Backup and Recovery Documents/Restore_and_Recover_Guide.md](docs/Backup%20and%20Recovery%20Documents/Restore_and_Recover_Guide.md) | Step-by-step restore procedures |

### Testing

| File | Purpose |
|---|---|
| [docs/Testing Documents/HARDENING_CC.md](docs/Testing%20Documents/HARDENING_CC.md) | Security hardening test results |
| [docs/Testing Documents/ADDITIONAL_AWS_TESTS.md](docs/Testing%20Documents/ADDITIONAL_AWS_TESTS.md) | AWS environment validation tests |
| [docs/Testing Documents/DISASTER_RECOVERY_TEST.md](docs/Testing%20Documents/DISASTER_RECOVERY_TEST.md) | Disaster recovery test results |
| [docs/Testing Documents/VALIDATION_REPORT_v7.4.0CC.md](docs/Testing%20Documents/VALIDATION_REPORT_v7.4.0CC.md) | Validation report v7.4.0 |
| [docs/Testing Documents/TEST_RESULTS_6.0.0CC.md](docs/Testing%20Documents/TEST_RESULTS_6.0.0CC.md) | Test results v6.0.0 |
| [docs/Testing Documents/user_ui_tests.md](docs/Testing%20Documents/user_ui_tests.md) | UI/UX test cases |

### Video and Demo

| File | Purpose |
|---|---|
| [docs/VIDEO_SCRIPTS.md](docs/VIDEO_SCRIPTS.md) | Terminal demo scripts for Videos 1 and 2 (Manners scoring, trust promotion) |
| [docs/VIDEO_CLAUDE_DESKTOP.md](docs/VIDEO_CLAUDE_DESKTOP.md) | Video 3 script — Claude Desktop governed by TelsonBase via MCP |
| [docs/DIRECTORY_CONVENTIONS.md](docs/DIRECTORY_CONVENTIONS.md) | Repository directory naming and layout conventions |

---

## proof_sheets/ — Evidence Documents

773 evidence documents in two tiers. See the master index for full details.

| Index | Contents |
|---|---|
| [proof_sheets/INDEX.md](proof_sheets/INDEX.md) | Master index — 52 claim-level sheets + 721 individual test sheets across 15 domains |

Claim-level sheets (`TB-PROOF-NNN`): one per logical capability claim, with source files, verification commands, and verdicts.

Individual test sheets (`TB-TEST-[DOMAIN]-NNN`): one per test function across sec, qms, tool, ocl, and 11 other domains.

---

*TelsonBase v11.0.1 · Quietfire AI · Apache 2.0*
